# Criado por José Eduardo Santana Martins
# Este arquivo serve para concentrar as regras do Módulo Melhorias: envio de sugestões, triagem, avisos, tarefa e relatórios.
"""Regras do Módulo Melhorias.

**Quem faz o quê (recurso `melhorias` da ACL):**
- qualquer usuário logado envia sugestões e acompanha as próprias em "Minhas sugestões";
- `CONTROLE_TOTAL` (e o SuperRoot) faz a triagem: situação, resposta ao autor, observação interna, tarefa e relatórios.
  Sem regras cadastradas no recurso, só o SuperRoot faz a triagem (ninguém vira triador por acaso).

**Avisos (caixa de Mensagens, com e-mail):** a sugestão nova vai a quem faz a triagem; a mudança de situação ou a
resposta vão ao autor. A observação interna nunca é mostrada ao autor.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.units import mm
from reportlab.platypus import Image as ImagemPdf
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.acl import NivelAcl
from app.models.melhorias import AnexoSugestao, EventoSugestao, SugestaoMelhoria
from app.models.tarefas import Tarefa
from app.models.usuario import Usuario
from app.services import servico_acl, servico_anexos, servico_mensagens
from app.services.documentos.pdf import FUSO_SAO_PAULO, DocumentoPdf
from app.services.documentos.planilha import Aba, Coluna, gerar_planilha
from app.services.noticias import imagens
from app.services.servico_auditoria import auditar
from app.services.tarefas import servico_tarefas

RECURSO = "melhorias"
MAXIMO_PRINTS = 3
ROTULOS_SITUACAO = {"nova": "Nova", "em_analise": "Em análise", "aceita": "Aceita", "recusada": "Recusada", "concluida": "Concluída"}
# Primeiro trecho da rota → módulo (o resto cai em "geral")
MODULOS_POR_ROTA = {
    "contratos": "contratos", "rh": "rh", "tarefas": "tarefas", "noticias": "noticias", "mensagens": "mensagens",
    "melhorias": "melhorias", "usuarios": "administracao", "setores": "administracao", "admin": "administracao", "perfil": "perfil",
}
ROTULOS_MODULO = {
    "contratos": "Contratos", "rh": "RH", "tarefas": "Tarefas", "noticias": "Notícias", "mensagens": "Mensagens",
    "melhorias": "Melhorias", "administracao": "Administração", "perfil": "Meu perfil", "portal": "Portal", "geral": "Geral",
}


class ErroMelhoria(Exception):
    """Regra do módulo violada (vira {"detalhe", "codigo"} na rota)."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido"):
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


@dataclass(frozen=True)
class Filtros:
    """Filtros da triagem (lista, planilha e PDF)."""

    busca: str = ""
    situacao: str | None = None
    modulo: str | None = None
    inicio: date | None = None
    fim: date | None = None


def _nome(usuario: Usuario | None) -> str:
    return (usuario.nome_completo or usuario.login) if usuario else "—"


def _local(valor: datetime | None) -> str:
    """Data e hora de São Paulo (dd/mm/aaaa hh:mm)."""
    if valor is None:
        return ""
    if valor.tzinfo is None:  # SQLite (testes) devolve sem fuso; tudo é gravado em UTC
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(FUSO_SAO_PAULO).strftime("%d/%m/%Y %H:%M")


def modulo_da_tela(tela: str) -> str:
    """Módulo a partir da rota (`/contratos/…` → `contratos`; `/` → `portal`)."""
    caminho = (tela or "").split("?")[0].split("#")[0].strip("/")
    if not caminho:
        return "portal" if tela else "geral"
    return MODULOS_POR_ROTA.get(caminho.split("/")[0], "geral")


# ---------------------------------------------------------------------------------------------
# Permissões
# ---------------------------------------------------------------------------------------------

def faz_triagem(sessao: Session, usuario: Usuario) -> bool:
    """SuperRoot ou CONTROLE_TOTAL em `melhorias` (recurso sem regras: só o SuperRoot)."""
    if usuario.superusuario:
        return True
    if not servico_acl.possui_regras(sessao, RECURSO):
        return False
    return servico_acl.resolver_acesso(sessao, usuario, RECURSO) == NivelAcl.CONTROLE_TOTAL


def exigir_triagem(sessao: Session, usuario: Usuario) -> None:
    if not faz_triagem(sessao, usuario):
        raise ErroMelhoria("A triagem de melhorias exige CONTROLE_TOTAL em 'melhorias'.", 403, "acl_negado")


def triadores(sessao: Session) -> list[Usuario]:
    """Quem recebe o aviso de sugestão nova (ativos com triagem)."""
    return [u for u in sessao.scalars(select(Usuario).where(Usuario.ativo.is_(True))) if faz_triagem(sessao, u)]


# ---------------------------------------------------------------------------------------------
# Envio e consulta do autor
# ---------------------------------------------------------------------------------------------

def registrar(sessao: Session, autor: Usuario, texto: str, tela: str, arquivos: list[tuple[str, bytes]]) -> SugestaoMelhoria:
    """Grava a sugestão (com até 3 prints conferidos pelo conteúdo) e avisa quem faz a triagem."""
    if len(arquivos) > MAXIMO_PRINTS:
        raise ErroMelhoria(f"Anexe no máximo {MAXIMO_PRINTS} prints.")
    numero = (sessao.scalar(select(func.max(SugestaoMelhoria.numero))) or 0) + 1
    sugestao = SugestaoMelhoria(
        numero=numero, autor_id=autor.id, autor_nome=_nome(autor), autor_login=autor.login, texto=texto, tela=tela[:1000],
        modulo=modulo_da_tela(tela), situacao="nova", resposta_publica="", observacao_interna="", atualizado_por_nome="",
        criado_em=agora_utc(),
    )
    for ordem, (nome, conteudo) in enumerate(arquivos):
        if len(conteudo) > servico_anexos.tamanho_maximo():
            raise ErroMelhoria(f"{nome}: o arquivo passa do limite de tamanho.")
        try:
            _, tipo = imagens.abrir(conteudo)
        except imagens.ErroImagem as erro:
            raise ErroMelhoria(f"{nome}: {erro}") from erro
        extensao = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(tipo, ".png")
        nome_final = Path(nome or "print").stem[:200] + extensao
        anexo = servico_anexos.guardar_arquivo_gerado(sessao, conteudo, nome_final, tipo, "melhoria-print", autor.id)
        sugestao.anexos.append(AnexoSugestao(anexo=anexo, ordem=ordem))
    sessao.add(sugestao)
    sessao.flush()
    auditar(sessao, autor.login, "melhorias.enviar", f"Sugestão #{numero}", autor_id=autor.id, alvo_tipo="melhoria",
            alvo_id=sugestao.id, dados={"tela": sugestao.tela, "prints": len(arquivos)})
    resumo = texto if len(texto) <= 400 else texto[:400] + "…"
    servico_mensagens.notificar(
        sessao, [u.id for u in triadores(sessao)], f"Nova sugestão de melhoria #{numero} ({ROTULOS_MODULO[sugestao.modulo]})",
        f"{sugestao.autor_nome} enviou uma sugestão de melhoria.\n\nTela: {sugestao.tela or '—'}\n\n{resumo}",
        chave=f"melhoria-nova:{sugestao.id}", categoria="pendencia", link=f"/melhorias/triagem?sugestao={numero}", email=True, autor=autor,
    )
    return sugestao


def minhas(sessao: Session, usuario: Usuario, pagina: int, tamanho: int) -> tuple[list[SugestaoMelhoria], int]:
    consulta = select(SugestaoMelhoria).where(SugestaoMelhoria.autor_id == usuario.id)
    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    itens = list(sessao.scalars(consulta.order_by(SugestaoMelhoria.numero.desc()).offset((pagina - 1) * tamanho).limit(tamanho)))
    return itens, total


def por_numero(sessao: Session, numero: int) -> SugestaoMelhoria:
    sugestao = sessao.scalar(select(SugestaoMelhoria).where(SugestaoMelhoria.numero == numero))
    if sugestao is None:
        raise ErroMelhoria("Sugestão não encontrada.", 404, "nao_encontrado")
    return sugestao


def do_autor(sessao: Session, usuario: Usuario, numero: int) -> SugestaoMelhoria:
    """Sugestão do próprio usuário (de outra pessoa: 404, sem revelar que existe)."""
    sugestao = por_numero(sessao, numero)
    if sugestao.autor_id != usuario.id:
        raise ErroMelhoria("Sugestão não encontrada.", 404, "nao_encontrado")
    return sugestao


def print_para_download(sessao: Session, usuario: Usuario, numero: int, anexo_id) -> AnexoSugestao:
    """Print da sugestão: o autor ou quem faz a triagem."""
    sugestao = por_numero(sessao, numero)
    if sugestao.autor_id != usuario.id and not faz_triagem(sessao, usuario):
        raise ErroMelhoria("Sugestão não encontrada.", 404, "nao_encontrado")
    item = next((a for a in sugestao.anexos if a.anexo_id == anexo_id), None)
    if item is None:
        raise ErroMelhoria("Arquivo não encontrado.", 404, "nao_encontrado")
    return item


def numero_da_tarefa(sessao: Session, sugestao: SugestaoMelhoria) -> int | None:
    tarefa = sessao.get(Tarefa, sugestao.tarefa_id) if sugestao.tarefa_id else None
    return tarefa.numero if tarefa else None


# ---------------------------------------------------------------------------------------------
# Triagem
# ---------------------------------------------------------------------------------------------

def _consulta(filtros: Filtros, com_situacao: bool = True):
    consulta = select(SugestaoMelhoria)
    if filtros.busca.strip():
        termo = f"%{filtros.busca.strip()}%"
        condicoes = [SugestaoMelhoria.texto.ilike(termo), SugestaoMelhoria.autor_nome.ilike(termo), SugestaoMelhoria.autor_login.ilike(termo),
                     SugestaoMelhoria.tela.ilike(termo)]
        if filtros.busca.strip().lstrip("#").isdigit():
            condicoes.append(SugestaoMelhoria.numero == int(filtros.busca.strip().lstrip("#")))
        consulta = consulta.where(or_(*condicoes))
    if com_situacao and filtros.situacao:
        consulta = consulta.where(SugestaoMelhoria.situacao == filtros.situacao)
    if filtros.modulo:
        consulta = consulta.where(SugestaoMelhoria.modulo == filtros.modulo)
    # Período em dias de São Paulo (limites inclusivos)
    if filtros.inicio:
        consulta = consulta.where(SugestaoMelhoria.criado_em >= datetime.combine(filtros.inicio, datetime.min.time(), FUSO_SAO_PAULO))
    if filtros.fim:
        consulta = consulta.where(SugestaoMelhoria.criado_em < datetime.combine(filtros.fim + timedelta(days=1), datetime.min.time(), FUSO_SAO_PAULO))
    return consulta


def listar(sessao: Session, filtros: Filtros, pagina: int, tamanho: int) -> tuple[list[SugestaoMelhoria], int, dict[str, int], list[str]]:
    consulta = _consulta(filtros)
    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    itens = list(sessao.scalars(consulta.order_by(SugestaoMelhoria.numero.desc()).offset((pagina - 1) * tamanho).limit(tamanho)))
    # Totais por situação com os demais filtros (os selos da tela)
    base = _consulta(filtros, com_situacao=False).subquery()
    totais = {s: 0 for s in ROTULOS_SITUACAO}
    for situacao, quantidade in sessao.execute(select(base.c.situacao, func.count()).group_by(base.c.situacao)):
        totais[situacao] = quantidade
    modulos = sorted(sessao.scalars(select(SugestaoMelhoria.modulo).distinct()))
    return itens, total, totais, modulos


def _evento(sessao: Session, sugestao: SugestaoMelhoria, descricao: str, autor: Usuario, anterior: str = "", nova: str = "") -> None:
    sugestao.eventos.append(EventoSugestao(descricao=descricao[:500], situacao_anterior=anterior, situacao_nova=nova, autor_id=autor.id,
                                           autor_nome=_nome(autor), criado_em=agora_utc()))


def tratar(sessao: Session, numero: int, situacao: str, resposta: str, observacao: str, usuario: Usuario) -> SugestaoMelhoria:
    """Grava a triagem; se a situação ou a resposta mudarem, avisa o autor."""
    sugestao = por_numero(sessao, numero)
    resposta, observacao = resposta.strip(), observacao.strip()
    anterior = sugestao.situacao
    mudou_situacao, mudou_resposta = situacao != anterior, resposta != sugestao.resposta_publica
    if not (mudou_situacao or mudou_resposta or observacao != sugestao.observacao_interna):
        return sugestao
    sugestao.situacao, sugestao.resposta_publica, sugestao.observacao_interna = situacao, resposta, observacao
    sugestao.atualizado_em, sugestao.atualizado_por_id, sugestao.atualizado_por_nome = agora_utc(), usuario.id, _nome(usuario)
    partes = []
    if mudou_situacao:
        partes.append(f"Situação: {ROTULOS_SITUACAO[anterior]} → {ROTULOS_SITUACAO[situacao]}")
    if mudou_resposta:
        partes.append("Resposta ao autor atualizada" if resposta else "Resposta ao autor removida")
    if not partes:
        partes.append("Observação interna atualizada")
    _evento(sessao, sugestao, "; ".join(partes), usuario, anterior if mudou_situacao else "", situacao if mudou_situacao else "")
    auditar(sessao, usuario.login, "melhorias.tratar", f"Sugestão #{numero}", autor_id=usuario.id, alvo_tipo="melhoria", alvo_id=sugestao.id,
            dados={"situacao": situacao, "anterior": anterior, "resposta_alterada": mudou_resposta})
    if (mudou_situacao or (mudou_resposta and resposta)) and sugestao.autor_id:
        corpo = f"Sua sugestão de melhoria #{numero} está agora: {ROTULOS_SITUACAO[situacao]}."
        if resposta:
            corpo += f"\n\nResposta da equipe:\n{resposta}"
        corpo += f"\n\nSua sugestão:\n{sugestao.texto if len(sugestao.texto) <= 400 else sugestao.texto[:400] + '…'}"
        sessao.flush()
        servico_mensagens.notificar(
            sessao, [sugestao.autor_id], f"Sugestão de melhoria #{numero}: {ROTULOS_SITUACAO[situacao]}", corpo,
            chave=f"melhoria-tratada:{sugestao.id}:{len(sugestao.eventos)}", link=f"/melhorias?sugestao={numero}", email=True, autor=usuario,
        )
    return sugestao


def converter_em_tarefa(sessao: Session, numero: int, titulo: str, prazo: datetime, prioridade: str, equipe_id, responsavel_id: int | None,
                        usuario: Usuario) -> tuple[SugestaoMelhoria, Tarefa]:
    """Cria a tarefa no Módulo Tarefas com o texto e o link da sugestão; a sugestão fica Aceita."""
    sugestao = por_numero(sessao, numero)
    if sugestao.tarefa_id and sessao.get(Tarefa, sugestao.tarefa_id):
        raise ErroMelhoria(f"A sugestão já virou a tarefa #{numero_da_tarefa(sessao, sugestao)}.", 409, "conflito")
    descricao = (f"Sugestão de melhoria #{numero}, enviada por {sugestao.autor_nome} em {_local(sugestao.criado_em)}.\n"
                 f"Tela: {sugestao.tela or '—'}\n\n{sugestao.texto}")
    try:
        tarefa = servico_tarefas.criar(sessao, usuario, servico_tarefas.DadosTarefa(
            titulo=titulo.strip(), descricao=descricao, prazo=prazo, prioridade=prioridade, equipe_id=equipe_id, responsavel_id=responsavel_id))
    except servico_tarefas.ErroTarefa as erro:
        raise ErroMelhoria(str(erro), erro.status, erro.codigo) from erro
    sugestao.tarefa_id = tarefa.id
    anterior = sugestao.situacao
    if anterior in ("nova", "em_analise"):
        sugestao.situacao = "aceita"
    sugestao.atualizado_em, sugestao.atualizado_por_id, sugestao.atualizado_por_nome = agora_utc(), usuario.id, _nome(usuario)
    _evento(sessao, sugestao, f"Convertida na tarefa #{tarefa.numero}", usuario, anterior if sugestao.situacao != anterior else "",
            sugestao.situacao if sugestao.situacao != anterior else "")
    auditar(sessao, usuario.login, "melhorias.tarefa", f"Sugestão #{numero}", autor_id=usuario.id, alvo_tipo="melhoria", alvo_id=sugestao.id,
            dados={"tarefa": tarefa.numero})
    if sugestao.situacao != anterior and sugestao.autor_id:
        sessao.flush()
        servico_mensagens.notificar(
            sessao, [sugestao.autor_id], f"Sugestão de melhoria #{numero}: Aceita",
            f"Sua sugestão de melhoria #{numero} foi aceita e entrou na fila de trabalho da equipe.", chave=f"melhoria-tratada:{sugestao.id}:{len(sugestao.eventos)}",
            link=f"/melhorias?sugestao={numero}", email=True, autor=usuario,
        )
    return sugestao, tarefa


# ---------------------------------------------------------------------------------------------
# Planilha e relatório em PDF
# ---------------------------------------------------------------------------------------------

def _todas(sessao: Session, filtros: Filtros) -> list[SugestaoMelhoria]:
    return list(sessao.scalars(_consulta(filtros).order_by(SugestaoMelhoria.numero.desc())))


def _descricao_filtros(filtros: Filtros) -> str:
    partes = []
    if filtros.busca.strip():
        partes.append(f"busca \"{filtros.busca.strip()}\"")
    if filtros.situacao:
        partes.append(f"situação {ROTULOS_SITUACAO.get(filtros.situacao, filtros.situacao)}")
    if filtros.modulo:
        partes.append(f"módulo {ROTULOS_MODULO.get(filtros.modulo, filtros.modulo)}")
    if filtros.inicio or filtros.fim:
        partes.append(f"período {filtros.inicio:%d/%m/%Y} a {filtros.fim:%d/%m/%Y}" if filtros.inicio and filtros.fim
                      else f"desde {filtros.inicio:%d/%m/%Y}" if filtros.inicio else f"até {filtros.fim:%d/%m/%Y}")
    return "Filtros: " + ", ".join(partes) if partes else "Todas as sugestões"


def planilha(sessao: Session, filtros: Filtros) -> bytes:
    lista = _todas(sessao, filtros)
    colunas = [Coluna("Nº", largura=7), Coluna("Enviada em", largura=17), Coluna("Autor", largura=28), Coluna("Login", largura=16),
               Coluna("Módulo", largura=14), Coluna("Tela", largura=34), Coluna("Sugestão", largura=70), Coluna("Situação", largura=13),
               Coluna("Resposta ao autor", largura=50), Coluna("Observação interna", largura=50), Coluna("Tarefa", largura=9),
               Coluna("Prints", largura=8), Coluna("Tratada por", largura=26), Coluna("Tratada em", largura=17)]
    linhas = [[s.numero, _local(s.criado_em), s.autor_nome, s.autor_login, ROTULOS_MODULO.get(s.modulo, s.modulo), s.tela, s.texto,
               ROTULOS_SITUACAO[s.situacao], s.resposta_publica, s.observacao_interna,
               (f"#{numero_da_tarefa(sessao, s)}" if s.tarefa_id else ""), len(s.anexos), s.atualizado_por_nome, _local(s.atualizado_em)]
              for s in lista]
    return gerar_planilha([Aba(nome="Melhorias", colunas=colunas, linhas=linhas, titulo=f"Sugestões de melhoria — {_descricao_filtros(filtros)}")])


def relatorio_pdf(sessao: Session, filtros: Filtros, autor: Usuario) -> bytes:
    """Relatório: totais por situação e por módulo e uma seção por sugestão, com os prints."""
    lista = _todas(sessao, filtros)
    documento = DocumentoPdf(titulo="Relatório de sugestões de melhoria", subtitulo=f"{_descricao_filtros(filtros)} · {len(lista)} sugestão(ões)",
                             autor=_nome(autor))
    por_situacao = {s: sum(1 for x in lista if x.situacao == s) for s in ROTULOS_SITUACAO}
    por_modulo: dict[str, int] = {}
    for s in lista:
        por_modulo[s.modulo] = por_modulo.get(s.modulo, 0) + 1
    documento.secao("Resumo")
    documento.tabela(["Situação", "Quantidade"], [[ROTULOS_SITUACAO[s], str(q)] for s, q in por_situacao.items()], larguras=[3, 1],
                     alinhar_direita=[1], rodape=["Total", str(len(lista))])
    documento.espaco()
    documento.tabela(["Módulo", "Quantidade"], [[ROTULOS_MODULO.get(m, m), str(q)] for m, q in sorted(por_modulo.items(), key=lambda x: -x[1])],
                     larguras=[3, 1], alinhar_direita=[1])
    for s in lista:
        documento.secao(f"#{s.numero} · {ROTULOS_SITUACAO[s.situacao]} · {ROTULOS_MODULO.get(s.modulo, s.modulo)}")
        tarefa = numero_da_tarefa(sessao, s)
        documento.campos([("Autor", f"{s.autor_nome} ({s.autor_login})"), ("Enviada em", _local(s.criado_em)), ("Tela", s.tela or "—"),
                          ("Tarefa", f"#{tarefa}" if tarefa else "—"), ("Tratada por", s.atualizado_por_nome or "—"),
                          ("Tratada em", _local(s.atualizado_em) or "—")])
        documento.paragrafo(f"<b>Sugestão:</b> {_html(s.texto)}")
        if s.resposta_publica:
            documento.paragrafo(f"<b>Resposta ao autor:</b> {_html(s.resposta_publica)}")
        if s.observacao_interna:
            documento.paragrafo(f"<b>Observação interna:</b> {_html(s.observacao_interna)}")
        for item in s.anexos:
            figura = _miniatura(item)
            if figura is not None:
                documento.espaco(2).bloco(figura)
        documento.espaco()
    return documento.gerar()


def _html(texto: str) -> str:
    return escape(texto).replace("\n", "<br/>")


def _miniatura(item: AnexoSugestao) -> ImagemPdf | None:
    """Print reduzido para caber no relatório (até 120 × 70 mm, sem distorcer)."""
    arquivo = servico_anexos.caminho(item.anexo)
    if item.anexo.excluido_em is not None or not arquivo.is_file():
        return None
    try:
        figura, _ = imagens.abrir(arquivo.read_bytes())
    except imagens.ErroImagem:
        return None
    escala = min(120 * mm / figura.width, 70 * mm / figura.height, 1.0)
    saida = BytesIO()
    figura.save(saida, "PNG")
    saida.seek(0)
    return ImagemPdf(saida, width=figura.width * escala, height=figura.height * escala, hAlign="LEFT")
