# Criado por José Eduardo Santana Martins
# Este arquivo serve para ler um Word (.docx) de ETP ou TR e transformá-lo na árvore de seções e itens, com prévia antes de gravar.
"""Importação de Word.

O leitor é determinístico: estilos conhecidos (`Nível 01`..`Nível 04`) e a numeração do texto (`1.1.`, `I -`, `a)`) formam a hierarquia e
qualquer ambiguidade vira item marcado como **precisa de revisão**. Os comentários do Word entram como somente leitura, ligados ao
primeiro bloco que o comentário atinge. O arquivo é inspecionado antes (limites de tamanho, parágrafos, itens e comentários, e proteção
contra ZIP bomb).

`ler()` devolve a prévia (nada é gravado); `gravar()` cria o documento a partir dela.
"""

import hashlib
import re
import unicodedata
import uuid
import zipfile
from datetime import datetime
from html import escape
from io import BytesIO

from lxml import etree
from sqlalchemy.orm import Session

from app.models.contratacoes import ComentarioImportado, DocumentoContratacao, ItemContratacao, SecaoContratacao
from app.models.usuario import Usuario
from app.services.servico_auditoria import auditar
from app.services.contratacoes import conteudo, versoes
from app.services.contratacoes.acesso import ErroContratacao

LIMITE_ARQUIVO = 10 * 1024 * 1024
LIMITE_EXPANDIDO = 50 * 1024 * 1024
MAX_PARAGRAFOS = 5000
MAX_ITENS = 5000
MAX_SECOES = 200
MAX_PROFUNDIDADE = 8
MAX_COMENTARIOS = 5000
MAX_COMENTARIOS_POR_ITEM = 100
MAX_TEXTO_COMENTARIO = 4000
MAX_TRECHO = 2000

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"w": W}
RE_NUMERO_INICIAL = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?|[IVXLCDM]+[.)]|[a-z][.)])\s*", re.I)
RE_NUMERACAO = re.compile(r"^\s*(\d+(?:\.\d+)+)[.)]?\s+")
RE_SECAO = re.compile(r"^\s*\d+\.\s+\S")
RE_ROMANO = re.compile(r"^\s*[IVXLCDM]+\s*[.)\-–:]\s+", re.I)
RE_LETRA = re.compile(r"^\s*[a-z]\s*[.)\-–:]\s+", re.I)
RE_CABECALHO = re.compile(r"^(ETP|TR|Processo|Link)\s*[-:]\s*(.*)$")
RE_OU = re.compile(r"^\s*OU(?:\s|$)", re.I)
RE_MARCADOR = re.compile(r"\[[^\]]+\]|<[^>]+>|_{3,}")
RE_NOTA = re.compile(r"^(nota|observa[cç][aã]o|orienta[cç][aã]o|instru[cç][aã]o)\b", re.I)
VERMELHOS = {"FF0000", "C00000", "C62828"}
REALCES = {"yellow": "#ffff00", "green": "#00ff00", "cyan": "#00ffff", "magenta": "#ff00ff", "blue": "#0000ff", "red": "#ff0000",
           "darkYellow": "#808000", "gray": "#808080", "lightGray": "#c0c0c0"}


def _q(nome: str) -> str:
    return f"{{{W}}}{nome}"


def _val(no, filho: str) -> str | None:
    el = no.find(f"w:{filho}", NS) if no is not None else None
    return el.get(_q("val")) if el is not None else None


def _normalizar_texto(valor: str) -> str:
    return re.sub(r"\s+", " ", valor.replace(" ", " ")).strip()


def _normalizar_estilo(estilo: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", estilo.lower()))


def _limitar(valor: str, maximo: int) -> str:
    return valor if len(valor) <= maximo else valor[:maximo]


def _curto(valor: str) -> str:
    return valor if len(valor) <= 80 else valor[:77] + "..."


def _texto(no) -> str:
    return "".join(t.text or "" for t in no.iter(_q("t")))


# --- Pacote -------------------------------------------------------------------------------------

def _validar_pacote(dados: bytes) -> zipfile.ZipFile:
    if len(dados) > LIMITE_ARQUIVO:
        raise ErroContratacao("O arquivo excede 10 MB.", 413, "arquivo_grande")
    try:
        pacote = zipfile.ZipFile(BytesIO(dados))
    except zipfile.BadZipFile as erro:
        raise ErroContratacao("O arquivo não é um DOCX válido.", 400, "docx_invalido") from erro
    nomes = {i.filename for i in pacote.infolist()}
    if "word/document.xml" not in nomes:
        raise ErroContratacao("O arquivo não é um DOCX válido.", 400, "docx_invalido")
    if any(n.endswith(".docm") or n.startswith("word/vbaProject") for n in nomes):
        raise ErroContratacao("Envie um documento DOCX sem macros.", 400, "docx_invalido")
    total = 0
    for i in pacote.infolist():
        total += i.file_size
        if total > LIMITE_EXPANDIDO:
            raise ErroContratacao("O conteúdo descompactado excede o limite de segurança.", 400, "docx_invalido")
        if ".." in i.filename or i.filename.startswith("/"):
            raise ErroContratacao("O pacote DOCX contém um caminho inválido.", 400, "docx_invalido")
    return pacote


def _xml(pacote: zipfile.ZipFile, caminho: str):
    try:
        dados = pacote.read(caminho)
    except KeyError:
        return None
    analisador = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    return etree.fromstring(dados, analisador)


def _links(pacote: zipfile.ZipFile) -> dict[str, str]:
    raiz = _xml(pacote, "word/_rels/document.xml.rels")
    saida: dict[str, str] = {}
    if raiz is not None:
        for rel in raiz:
            alvo = rel.get("Target") or ""
            if rel.get("TargetMode") == "External" and alvo.lower().startswith(("http://", "https://", "mailto:")):
                saida[rel.get("Id") or ""] = alvo
    return saida


# --- Comentários --------------------------------------------------------------------------------

def _bloco_raiz(no, corpo):
    atual = no
    while atual.getparent() is not None and atual.getparent() is not corpo:
        atual = atual.getparent()
    return atual if atual.getparent() is corpo else None


def _comentarios(pacote: zipfile.ZipFile, corpo) -> tuple[dict, list[dict], int]:
    raiz = _xml(pacote, "word/comments.xml")
    origem = {c.get(_q("id")): c for c in (raiz.findall("w:comment", NS) if raiz is not None else []) if c.get(_q("id")) is not None}
    blocos: dict[str, list] = {i: [] for i in origem}
    ancoras: dict[str, list[str]] = {i: [] for i in origem}
    ativos: set[str] = set()
    for no in corpo.iter():
        if no.tag == _q("commentRangeStart") and no.get(_q("id")) in origem:
            ativos.add(no.get(_q("id")))
        elif no.tag == _q("t"):
            bloco = _bloco_raiz(no, corpo)
            for i in ativos:
                ancoras[i].append(no.text or "")
                if bloco is not None and bloco not in blocos[i]:
                    blocos[i].append(bloco)
        elif no.tag == _q("commentReference") and no.get(_q("id")) in origem:
            bloco = _bloco_raiz(no, corpo)
            if bloco is not None and bloco not in blocos[no.get(_q("id"))]:
                blocos[no.get(_q("id"))].append(bloco)
        elif no.tag == _q("commentRangeEnd"):
            ativos.discard(no.get(_q("id")))
    filhos = list(corpo)
    por_bloco: dict = {}
    sem_ancora: list[dict] = []
    for i, c in origem.items():
        tocados = [b for b in filhos if b in blocos[i]]
        data = None
        if c.get(_q("date")):
            try:
                data = datetime.fromisoformat(c.get(_q("date")).replace("Z", "+00:00")).isoformat()
            except ValueError:
                data = None
        registro = {"id_externo": i, "autor": _normalizar_texto(c.get(_q("author")) or "Autor não informado"), "iniciais": c.get(_q("initials")),
                    "comentado_em": data, "comentario": _limitar(_normalizar_texto(_texto(c)), MAX_TEXTO_COMENTARIO),
                    "trecho": _limitar(_normalizar_texto("".join(ancoras[i])), MAX_TRECHO), "abrange_mais": len(tocados) > 1}
        if not tocados:
            sem_ancora.append(registro)
        else:
            por_bloco.setdefault(tocados[0], []).append(registro)
    return por_bloco, sem_ancora, len(origem)


# --- Conteúdo -----------------------------------------------------------------------------------

def _html_run(run, pular: list[int]) -> str:
    bruto = "".join(t.text or "" for t in run.iter(_q("t")))
    if pular[0] >= len(bruto) and bruto:
        pular[0] -= len(bruto)
        return ""
    if pular[0] > 0:
        bruto = bruto[pular[0]:]
        pular[0] = 0
    texto = escape(bruto)
    props = run.find("w:rPr", NS)
    if props is not None:
        if props.find("w:b", NS) is not None and _val(props, "b") not in ("0", "false"):
            texto = f"<strong>{texto}</strong>"
        if props.find("w:i", NS) is not None and _val(props, "i") not in ("0", "false"):
            texto = f"<em>{texto}</em>"
        if props.find("w:u", NS) is not None and _val(props, "u") not in ("none",):
            texto = f"<u>{texto}</u>"
        estilos = []
        cor = _val(props, "color")
        if cor and cor != "auto" and re.fullmatch(r"[0-9A-Fa-f]{6}", cor):
            estilos.append(f"color:#{cor}")
        realce = REALCES.get(_val(props, "highlight") or "")
        if realce:
            estilos.append(f"background-color:{realce}")
        if estilos:
            texto = f'<span style="{";".join(estilos)}">{texto}</span>'
    texto += "<br>" * len(run.findall("w:br", NS))
    return texto


def _html_paragrafo(par, pular: int, links: dict[str, str]) -> str:
    restante = [pular]
    saida = ["<p>"]
    for filho in par:
        if filho.tag == _q("r"):
            saida.append(_html_run(filho, restante))
        elif filho.tag == _q("hyperlink"):
            trecho = "".join(_html_run(r, restante) for r in filho.iter(_q("r")))
            url = links.get(filho.get(f"{{{R}}}id") or "")
            saida.append(f'<a href="{escape(url)}">{trecho}</a>' if url and trecho else trecho)
    saida.append("</p>")
    return "".join(saida)


def _html_tabela(tabela, links: dict[str, str]) -> str:
    saida = ["<table><tbody>"]
    for linha in tabela.findall("w:tr", NS):
        saida.append("<tr>")
        for celula in linha.findall("w:tc", NS):
            span = 1
            grade = celula.find("w:tcPr/w:gridSpan", NS)
            if grade is not None and (grade.get(_q("val")) or "").isdigit():
                span = max(1, min(int(grade.get(_q("val"))), 50))
            saida.append(f'<td colspan="{span}">' if span > 1 else "<td>")
            saida += [_html_paragrafo(p, 0, links) for p in celula.findall("w:p", NS)]
            saida.append("</td>")
        saida.append("</tr>")
    saida.append("</tbody></table>")
    return "".join(saida)


def _revisar(par, estilo: str, texto: str) -> bool:
    e = _normalizar_estilo(estilo)
    if "red" in e or e.endswith("r") and e.startswith(("nivel", "nvel")):
        return True
    for run in par.iter(_q("r")):
        cor = _val(run.find("w:rPr", NS), "color")
        if cor and cor.upper() in VERMELHOS:
            return True
    return bool(RE_OU.match(texto) or RE_MARCADOR.search(texto) or RE_NOTA.match(texto))


def _todo_em_negrito(par) -> bool:
    runs = [r for r in par.iter(_q("r")) if "".join(t.text or "" for t in r.iter(_q("t"))).strip()]
    return bool(runs) and all(r.find("w:rPr/w:b", NS) is not None and _val(r.find("w:rPr", NS), "b") not in ("0", "false") for r in runs)


# --- Classificação ------------------------------------------------------------------------------

def _tam_prefixo(texto: str) -> int:
    achado = RE_NUMERO_INICIAL.match(texto)
    return len(achado.group(0)) if achado else 0


def _pai_mais_proximo(pais: dict[int, str], nivel: int) -> str | None:
    for n in range(nivel, -1, -1):
        if n in pais:
            return pais[n]
    return None


def _classificar(estilo: str, texto: str, pais: dict[int, str]) -> tuple[str, int, str | None, int, bool]:
    """(tipo, profundidade, id do pai, tamanho do prefixo a remover, ambíguo)."""
    e = _normalizar_estilo(estilo)
    nivel = 0 if e.startswith(("nivel2", "nvel2")) else 1 if e.startswith(("nivel3", "nvel3")) else 2 if e.startswith(("nivel4", "nvel4")) else -1
    if nivel >= 0:
        return ("item" if nivel == 0 else "subitem"), nivel, _pai_mais_proximo(pais, nivel - 1), _tam_prefixo(texto), False
    proxima = min((max(pais) + 1) if pais else 0, MAX_PROFUNDIDADE)
    numerada = RE_NUMERACAO.match(texto)
    if numerada:
        partes = numerada.group(1).count(".") + 1
        profundidade = min(max(partes - 2, 0), MAX_PROFUNDIDADE)
        return ("item" if profundidade == 0 else "subitem"), profundidade, _pai_mais_proximo(pais, profundidade - 1), len(numerada.group(0)), False
    romano = RE_ROMANO.match(texto)
    if romano:
        return "inciso", proxima, _pai_mais_proximo(pais, proxima - 1), len(romano.group(0)), False
    letra = RE_LETRA.match(texto)
    if letra:
        return "alinea", proxima, _pai_mais_proximo(pais, proxima - 1), len(letra.group(0)), False
    return ("item" if proxima == 0 else "subitem"), proxima, _pai_mais_proximo(pais, proxima - 1), _tam_prefixo(texto), True


# --- Leitura ------------------------------------------------------------------------------------

def ler(dados: bytes, nome_arquivo: str) -> dict:
    """Prévia da importação: `{arquivo, sha256, secoes: [{id_cliente, titulo, itens: […]}], avisos, totais}`. Não grava nada."""
    pacote = _validar_pacote(dados)
    raiz = _xml(pacote, "word/document.xml")
    corpo = raiz.find("w:body", NS) if raiz is not None else None
    if corpo is None:
        raise ErroContratacao("O arquivo não possui um corpo de documento válido.", 400, "docx_invalido")
    por_bloco, sem_ancora, total_comentarios = _comentarios(pacote, corpo)
    if total_comentarios > MAX_COMENTARIOS:
        raise ErroContratacao(f"O documento excede o limite de {MAX_COMENTARIOS} comentários.", 400, "docx_invalido")
    if sum(1 for _ in corpo.iter(_q("p"))) > MAX_PARAGRAFOS:
        raise ErroContratacao(f"O documento excede o limite de {MAX_PARAGRAFOS} parágrafos.", 400, "docx_invalido")
    links = _links(pacote)

    secoes: list[dict] = []
    avisos: list[str] = []
    atual: dict | None = None
    pais: dict[int, str] = {}
    ordens: dict[str, int] = {}
    tabelas = 0
    pendentes: list[dict] = []
    cabecalho: dict[str, str] = {}

    def nova_secao(titulo: str) -> dict:
        if len(secoes) >= MAX_SECOES:
            raise ErroContratacao(f"O documento excede o limite de {MAX_SECOES} seções.", 400, "docx_invalido")
        secao = {"id_cliente": uuid.uuid4().hex, "titulo": titulo, "itens": []}
        secoes.append(secao)
        pais.clear()
        ordens.clear()
        return secao

    def levar_comentarios(proprios: list[dict]) -> list[dict]:
        todos = {c["id_externo"]: c for c in pendentes + proprios}.values()
        pendentes.clear()
        lista = list(todos)
        if len(lista) > MAX_COMENTARIOS_POR_ITEM:
            raise ErroContratacao(f"Um item excede o limite de {MAX_COMENTARIOS_POR_ITEM} comentários.", 400, "docx_invalido")
        return lista

    def proxima_ordem(pai: str | None) -> int:
        chave = pai or "raiz"
        ordens[chave] = ordens.get(chave, 0) + 1
        return ordens[chave]

    for elemento in corpo:
        proprios = por_bloco.get(elemento, [])
        if elemento.tag == _q("p"):
            texto = _normalizar_texto(_texto(elemento))
            if not texto:
                pendentes += proprios
                continue
            estilo = _val(elemento.find("w:pPr", NS), "pStyle") or ""
            e = _normalizar_estilo(estilo)
            if e in ("nivel01", "nvel01") or (RE_SECAO.match(texto) and not RE_NUMERACAO.match(texto) and _todo_em_negrito(elemento)):
                atual = nova_secao(RE_NUMERO_INICIAL.sub("", texto, count=1).strip())
                pendentes += proprios
                continue
            if atual is None:
                # Cabeçalho gerado pela exportação (título, processo, link): não vira item
                cab = RE_CABECALHO.match(texto)
                if cab:
                    if cab.group(1).lower() == "processo":
                        cabecalho["processo"] = cab.group(2).strip()
                    elif cab.group(1).lower() not in ("link",):
                        cabecalho["nome"] = cab.group(2).strip()
                    continue
                atual = nova_secao("Informações iniciais")
            tipo, profundidade, pai, prefixo, ambiguo = _classificar(estilo, texto, pais)
            limpo = texto[prefixo:].strip()
            if not limpo:
                pendentes += proprios
                continue
            id_cliente = uuid.uuid4().hex
            aviso = "Hierarquia inferida; confira este item." if ambiguo else None
            atual["itens"].append({
                "id_cliente": id_cliente, "pai_id_cliente": pai, "tipo": tipo, "ordem": proxima_ordem(pai), "conteudo": limpo,
                "conteudo_html": _html_paragrafo(elemento, prefixo, links), "precisa_revisao": ambiguo or _revisar(elemento, estilo, limpo),
                "aviso": aviso, "comentarios": levar_comentarios(proprios)})
            pais[profundidade] = id_cliente
            for n in [n for n in pais if n > profundidade]:
                del pais[n]
            if aviso and len(avisos) < 100:
                avisos.append(f"{atual['titulo']}: {_curto(limpo)}")
        elif elemento.tag == _q("tbl"):
            if atual is None:
                atual = nova_secao("Informações iniciais")
            tabelas += 1
            pai = pais[max(pais)] if pais else None
            texto = _normalizar_texto("\n".join("\t".join(_normalizar_texto(_texto(c)) for c in l.findall("w:tc", NS)) for l in elemento.findall("w:tr", NS)))
            atual["itens"].append({
                "id_cliente": uuid.uuid4().hex, "pai_id_cliente": pai, "tipo": "subitem", "ordem": proxima_ordem(pai), "conteudo": texto or "Tabela importada",
                "conteudo_html": _html_tabela(elemento, links), "precisa_revisao": True, "aviso": "Tabela importada; confira células e mesclagens.",
                "comentarios": levar_comentarios(proprios)})

    for c in {c["id_externo"]: c for c in pendentes + sem_ancora}.values():
        if len(avisos) < 100:
            avisos.append(f"Comentário de {c['autor']} sem item associável: {_curto(c['comentario'])}")
    total_itens = sum(len(s["itens"]) for s in secoes)
    if not secoes or total_itens == 0:
        raise ErroContratacao("Não foi possível identificar conteúdo importável no documento.", 400, "docx_vazio")
    if total_itens > MAX_ITENS:
        raise ErroContratacao(f"O documento excede o limite de {MAX_ITENS} itens.", 400, "docx_invalido")
    for s in secoes:
        for i in s["itens"]:
            for c in i["comentarios"]:
                if c["abrange_mais"] and len(avisos) < 100:
                    avisos.append(f"{s['titulo']}: comentário de {c['autor']} abrange conteúdo além de {_curto(i['conteudo'])}")
    return {"arquivo": nome_arquivo, "nome_sugerido": cabecalho.get("nome", ""), "processo_sugerido": cabecalho.get("processo", ""), "sha256": hashlib.sha256(dados).hexdigest(), "secoes": secoes, "avisos": list(dict.fromkeys(avisos)),
            "totais": {"secoes": len(secoes), "itens": total_itens, "tabelas": tabelas, "para_revisar": sum(1 for s in secoes for i in s["itens"] if i["precisa_revisao"]),
                       "comentarios": sum(len(i["comentarios"]) for s in secoes for i in s["itens"])}}


# --- Gravação -----------------------------------------------------------------------------------

def gravar(sessao: Session, previa: dict, tipo: str, nome: str, processo: str, link_sei: str | None, autor: Usuario) -> DocumentoContratacao:
    """Cria o documento (rascunho, do autor) com as seções e itens da prévia e uma versão "Importação do Word"."""
    from app.services.contratacoes import arvore

    documento = arvore.criar_documento(sessao, tipo, nome, processo, link_sei, autor)
    for ordem, secao in enumerate(previa["secoes"], start=1):
        nova = SecaoContratacao(documento_id=documento.id, ordem=ordem, titulo=_limitar(secao["titulo"], 300))
        sessao.add(nova)
        sessao.flush()
        ids: dict[str, uuid.UUID] = {}
        for i in secao["itens"]:  # os pais sempre vêm antes dos filhos
            try:
                texto, html = conteudo.normalizar(i["conteudo"], i["conteudo_html"])
            except conteudo.ErroConteudo:
                texto, html = conteudo.normalizar(i["conteudo"], None)
            item = ItemContratacao(secao_id=nova.id, pai_id=ids.get(i["pai_id_cliente"]) if i["pai_id_cliente"] else None, tipo=i["tipo"], ordem=i["ordem"],
                                   conteudo=texto, conteudo_html=html, precisa_revisao=bool(i["precisa_revisao"]))
            sessao.add(item)
            sessao.flush()
            ids[i["id_cliente"]] = item.id
            for c in i["comentarios"]:
                data = None
                if c.get("comentado_em"):
                    try:
                        data = datetime.fromisoformat(c["comentado_em"])
                    except ValueError:
                        data = None
                sessao.add(ComentarioImportado(item_id=item.id, id_externo=c["id_externo"], autor=c["autor"], iniciais=c.get("iniciais"), comentado_em=data,
                                               comentario=c["comentario"], trecho=c["trecho"], abrange_mais=bool(c["abrange_mais"])))
    versoes.registrar(sessao, documento, "importacao", autor, f"Importado de {previa['arquivo']}")
    auditar(sessao, autor.login, "contratacao.importar", f"{documento.nome} ({previa['arquivo']})", autor_id=autor.id, alvo_tipo="contratacao", alvo_id=documento.id)
    sessao.commit()
    return documento
