# Criado por José Eduardo Santana Martins
# Este arquivo serve para importar o histórico de chamados do GLPI (10 ou 11) para o módulo Chamados, a partir de um dump do banco.
"""Importação do histórico do GLPI.

**Nunca lê o GLPI em produção:** a entrada é um arquivo de dump do MariaDB (`mysqldump`, com dados) feito pela equipe do GLPI, e,
para os anexos, uma cópia da pasta `files/`. O dump é lido direto do arquivo (não precisa de um MariaDB local).

Duas etapas, pelo script `scripts/migrar-chamados-glpi.py`:
1. **preparar**: lê o dump e escreve as tabelas de-para para revisão (`usuarios.csv`, `grupos.csv`, `etiquetas.csv`), já com sugestões;
2. **carregar**: aplica o dump com o de-para revisado. Por padrão é **ensaio** (carrega, conta e desfaz); `--gravar` grava.

Regras:
- **Idempotente:** cada linha guarda o id de origem (`origem_glpi_id`); o que já foi importado é pulado. Rodar de novo só traz o que falta.
- Categorias do GLPI viram **categorias ITIL**; o assunto dos importados é "Importados do GLPI" (inativo).
- Também serve à migração pelo botão (`migracao_glpi.py`): de-para automático (`mapas_automaticos`), modo `atualizar`, aviso de andamento e
  `apagar_chamados` (o "Refazer do zero" apaga todos os chamados, inclusive os abertos no SGI).
- O chamado mantém o **número do GLPI**; os novos continuam depois do maior (`proximo_numero`).
- O **resolvido** no GLPI entra como histórico **somente leitura** (`importado`); o **ainda aberto** entra como chamado normal do SGI (painel,
  fila, assumir, responder, resolver) e, depois de trabalhado aqui (a versão subiu), a migração não o sobrescreve mais. O SLA **não é
  recalculado**: os prazos e as datas são os do GLPI.
- Nenhum aviso, e-mail ou evento ao vivo é disparado.
- Datas do GLPI são do horário de São Paulo (sem fuso no banco) e viram UTC.
- GLPI 10 × 11: a versão vem de `glpi_configs`; o alvo da aprovação é `users_id_validate` (10) ou `itemtype_target/items_id_target` (11).
- Etiquetas (plugin tag), que a equipe usava como "nome do técnico", viram atribuição real conforme o de-para: `responsavel:<login>`,
  `setor:<nome do setor>` ou `nota` (registro na linha do tempo).
"""

import csv
import html
import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import FUSO_SAO_PAULO
from app.models.chamados import (
    STATUS_EM_APROVACAO, STATUS_EM_ATENDIMENTO, STATUS_NOVO, STATUS_PENDENTE, STATUS_SOLUCIONADO, AcompanhamentoChamado, AnexoChamado, AtorChamado,
    CategoriaChamados, CategoriaItilChamados, Chamado, SatisfacaoChamado, SolucaoChamado, TarefaChamado, ValidacaoChamado,
)
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.services import servico_anexos
from app.services.chamados import parametros
from app.services.chamados.painel import primeiros_nomes
from app.services.chamados.servico import CATEGORIA_ANEXO, ErroChamado, preparar_texto

# Tabelas lidas do dump (as demais linhas do arquivo são puladas sem guardar nada na memória)
TABELAS = {
    "glpi_configs", "glpi_users", "glpi_useremails", "glpi_groups", "glpi_itilcategories", "glpi_locations", "glpi_tickets", "glpi_tickets_users",
    "glpi_groups_tickets", "glpi_itilfollowups", "glpi_itilsolutions", "glpi_tickettasks", "glpi_ticketvalidations", "glpi_documents",
    "glpi_documents_items", "glpi_plugin_tag_tags", "glpi_plugin_tag_tagitems", "glpi_ticketsatisfactions",
}
# Status do GLPI → status-base (3 "planejado" é atendimento; 6 "fechado" não existe aqui: solucionado é o fim)
STATUS = {1: STATUS_NOVO, 2: STATUS_EM_ATENDIMENTO, 3: STATUS_EM_ATENDIMENTO, 4: STATUS_PENDENTE, 5: STATUS_SOLUCIONADO, 6: STATUS_SOLUCIONADO,
          10: STATUS_EM_APROVACAO}
# Prioridade 1 (muito baixa) a 6 (maior) → as quatro do SGI
PRIORIDADE = {1: "baixa", 2: "baixa", 3: "normal", 4: "alta", 5: "urgente", 6: "urgente"}
VALIDACAO = {2: "aguardando", 3: "aprovada", 4: "recusada"}
# Papel do ator no GLPI: 1 requerente, 2 atribuído, 3 observador
REQUERENTE, ATRIBUIDO, OBSERVADOR = 1, 2, 3
SEPARADOR_CSV = ";"


class ErroImportacao(Exception):
    """Entrada inválida (dump sem as tabelas, de-para com erro). A mensagem diz o que corrigir."""


# ---------------------------------------------------------------------------------------------
# Leitura do dump (mysqldump)
# ---------------------------------------------------------------------------------------------

_CREATE = re.compile(r"^CREATE TABLE `(\w+)`")
_COLUNA = re.compile(r"^\s+`(\w+)`")
_INSERT = re.compile(r"^INSERT INTO `(\w+)`(?: \(([^)]*)\))? VALUES ")
_ESCAPES = {"0": "\0", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a", "b": "\b"}


def _tuplas(texto: str) -> Iterator[list]:
    """Valores de `(...),(...)` no formato do mysqldump: texto entre aspas simples com escapes de barra, NULL e números."""
    i, n = 0, len(texto)
    while i < n:
        while i < n and texto[i] != "(":
            i += 1
        if i >= n:
            return
        i += 1
        linha: list = []
        while True:
            while texto[i] == " ":
                i += 1
            if texto[i] == "'":
                i += 1
                partes, inicio = [], i
                while True:
                    c = texto[i]
                    if c == "\\":
                        partes.append(texto[inicio:i])
                        proximo = texto[i + 1]
                        partes.append(_ESCAPES.get(proximo, proximo))
                        i += 2
                        inicio = i
                    elif c == "'":
                        if i + 1 < n and texto[i + 1] == "'":
                            partes.append(texto[inicio:i + 1])
                            i += 2
                            inicio = i
                            continue
                        partes.append(texto[inicio:i])
                        i += 1
                        break
                    else:
                        i += 1
                linha.append("".join(partes))
            else:
                inicio = i
                while texto[i] not in ",)":
                    i += 1
                bruto = texto[inicio:i].strip()
                if bruto.upper() == "NULL":
                    linha.append(None)
                else:
                    try:
                        linha.append(int(bruto))
                    except ValueError:
                        try:
                            linha.append(float(bruto))
                        except ValueError:
                            linha.append(bruto)
            if texto[i] == ",":
                i += 1
                continue
            i += 1  # ")"
            yield linha
            break


def ler_dump(caminho: Path, tabelas: set[str] = TABELAS) -> dict[str, list[dict]]:
    """Linhas das `tabelas` pedidas, como dicionários coluna → valor. Aceita dump com ou sem a lista de colunas no INSERT."""
    colunas: dict[str, list[str]] = {}
    dados: dict[str, list[dict]] = defaultdict(list)
    atual: str | None = None
    with open(caminho, encoding="utf-8", errors="replace") as arquivo:
        for linha in arquivo:
            if atual is not None:
                if linha.startswith(")"):
                    atual = None
                elif (m := _COLUNA.match(linha)):
                    colunas[atual].append(m.group(1))
                continue
            if (m := _CREATE.match(linha)):
                atual = m.group(1)
                colunas[atual] = []
                continue
            if not linha.startswith("INSERT INTO"):
                continue
            m = _INSERT.match(linha)
            if not m or m.group(1) not in tabelas:
                continue
            tabela = m.group(1)
            nomes = [c.strip().strip("`") for c in m.group(2).split(",")] if m.group(2) else colunas.get(tabela)
            if not nomes:
                raise ErroImportacao(f"O dump tem dados de {tabela} sem o CREATE TABLE antes: gere o dump com a estrutura (sem --no-create-info).")
            for valores in _tuplas(linha[m.end():]):
                dados[tabela].append(dict(zip(nomes, valores)))
    if "glpi_tickets" not in colunas:
        raise ErroImportacao("Este arquivo não parece um dump do GLPI: não há a tabela glpi_tickets.")
    return dict(dados)


def versao(dados: dict[str, list[dict]]) -> str:
    return next((str(c["value"]) for c in dados.get("glpi_configs", []) if c.get("context") == "core" and c.get("name") == "version"), "desconhecida")


def _data(valor) -> datetime | None:
    """Data do GLPI (horário de São Paulo, sem fuso) → UTC. Datas vazias ou zeradas viram None."""
    if not valor or str(valor).startswith("0000"):
        return None
    try:
        return datetime.fromisoformat(str(valor)).replace(tzinfo=FUSO_SAO_PAULO).astimezone(UTC)
    except ValueError:
        return None


def _texto(conteudo) -> str:
    """HTML do GLPI (o 10 guarda com as entidades escapadas) já saneado como os textos do módulo."""
    bruto = str(conteudo or "")
    if "&lt;" in bruto and "<" not in bruto:
        bruto = html.unescape(bruto)
    try:
        limpo, _ = preparar_texto(bruto, obrigatorio=False)
    except ErroChamado:
        limpo = f"<p>{html.escape(re.sub(r'<[^>]+>', ' ', bruto))[:200000]}</p>"
    return limpo or "<p>(sem texto no GLPI)</p>"


def _normalizar(texto: str) -> str:
    import unicodedata
    return " ".join(unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower().split())


# ---------------------------------------------------------------------------------------------
# Etapa 1: de-para para revisão
# ---------------------------------------------------------------------------------------------

@dataclass
class Relatorio:
    """Contagens origem × destino e os avisos da carga (o script imprime e grava em arquivo)."""
    versao: str = ""
    origem: Counter = field(default_factory=Counter)
    destino: Counter = field(default_factory=Counter)
    pulados: Counter = field(default_factory=Counter)
    avisos: list[str] = field(default_factory=list)

    def texto(self) -> str:
        linhas = [f"GLPI {self.versao}", "", f"{'item':<28}{'no dump':>10}{'importados':>12}{'já existiam':>13}"]
        for chave in sorted(set(self.origem) | set(self.destino)):
            linhas.append(f"{chave:<28}{self.origem[chave]:>10}{self.destino[chave]:>12}{self.pulados[chave]:>13}")
        if self.avisos:
            linhas += ["", f"Avisos ({len(self.avisos)}):"] + [f"- {a}" for a in self.avisos[:500]]
            if len(self.avisos) > 500:
                linhas.append(f"... e mais {len(self.avisos) - 500}")
        return "\n".join(linhas)


def _escrever(caminho: Path, cabecalho: list[str], linhas: list[list]) -> None:
    with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=SEPARADOR_CSV)
        escritor.writerow(cabecalho)
        escritor.writerows(linhas)


def _ler(caminho: Path) -> list[dict]:
    if not caminho.exists():
        raise ErroImportacao(f"Falta o arquivo de-para {caminho.name}: rode a etapa preparar antes.")
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=SEPARADOR_CSV))


def _nome_glpi(u: dict) -> str:
    return " ".join(x for x in (u.get("firstname"), u.get("realname")) if x) or str(u.get("name") or "")


@dataclass
class _Sugestoes:
    usuarios: list[list]
    grupos: list[list]
    etiquetas: list[list]
    avisos: list[str]


def _sugestoes(sessao: Session, dados: dict[str, list[dict]]) -> _Sugestoes:
    """De-para sugerido: usuário pelo login (ou e-mail); grupo pelo nome do setor; etiqueta com o nome de uma única pessoa vira responsável."""
    usuarios_sgi = list(sessao.scalars(select(Usuario)))
    por_login = {u.login.lower(): u for u in usuarios_sgi}
    por_email = {(u.email or "").lower(): u for u in usuarios_sgi if u.email}
    emails = defaultdict(list)
    for e in dados.get("glpi_useremails", []):
        emails[e["users_id"]].append(str(e["email"] or ""))
    usuarios, avisos = [], []
    for u in dados.get("glpi_users", []):
        login = str(u.get("name") or "")
        par = por_login.get(login.lower()) or next((por_email[e.lower()] for e in emails[u["id"]] if e.lower() in por_email), None)
        usuarios.append([u["id"], login, _nome_glpi(u), ", ".join(emails[u["id"]]), par.login if par else ""])
        if par is None:
            avisos.append(f"Usuário do GLPI sem par no SGI: {login} (vira solicitante externo ou fica sem autor)")

    setores = list(sessao.scalars(select(Setor).where(Setor.ativo.is_(True))))
    por_nome = {_normalizar(s.nome): s for s in setores} | {_normalizar(s.sigla): s for s in setores if getattr(s, "sigla", None)}
    grupos = []
    for g in dados.get("glpi_groups", []):
        completo = str(g.get("completename") or g.get("name") or "")
        ultimo = completo.split(">")[-1].strip()
        par = por_nome.get(_normalizar(ultimo)) or por_nome.get(_normalizar(completo.split(">")[0].strip()))
        grupos.append([g["id"], completo, par.nome if par else ""])

    uso = Counter(t["plugin_tag_tags_id"] for t in dados.get("glpi_plugin_tag_tagitems", []) if t.get("itemtype") == "Ticket")
    por_nome_pessoa = defaultdict(list)
    for u in usuarios_sgi:
        nome = u.nome_completo or ""
        for chave in {_normalizar(nome), _normalizar(primeiros_nomes(nome)), _normalizar(nome.split(" ")[0] if nome else "")}:
            if chave:
                por_nome_pessoa[chave].append(u)
    etiquetas = []
    for t in dados.get("glpi_plugin_tag_tags", []):
        nome = str(t.get("name") or "")
        candidatos = por_nome_pessoa.get(_normalizar(nome), [])
        setor = por_nome.get(_normalizar(nome.split("-")[-1].strip())) if "-" in nome else por_nome.get(_normalizar(nome))
        acao = f"responsavel:{candidatos[0].login}" if len(candidatos) == 1 else f"setor:{setor.nome}" if setor else "nota"
        etiquetas.append([t["id"], nome, uso[t["id"]], acao])
    return _Sugestoes(usuarios, grupos, etiquetas, avisos)


def preparar(sessao: Session, dados: dict[str, list[dict]], pasta: Path) -> Relatorio:
    """Escreve `usuarios.csv`, `grupos.csv` e `etiquetas.csv` com sugestões; a pessoa revisa a coluna da direita antes de carregar."""
    pasta.mkdir(parents=True, exist_ok=True)
    rel = Relatorio(versao=versao(dados))
    sug = _sugestoes(sessao, dados)
    _escrever(pasta / "usuarios.csv", ["glpi_id", "login_glpi", "nome", "email", "login_sgi"], sug.usuarios)
    _escrever(pasta / "grupos.csv", ["glpi_id", "grupo", "setor_sgi"], sug.grupos)
    _escrever(pasta / "etiquetas.csv", ["glpi_id", "etiqueta", "chamados", "acao"], sug.etiquetas)
    rel.origem["usuários"], rel.origem["grupos"], rel.origem["etiquetas"] = len(sug.usuarios), len(sug.grupos), len(sug.etiquetas)
    rel.avisos.extend(sug.avisos)
    return rel


# ---------------------------------------------------------------------------------------------
# Etapa 2: carga
# ---------------------------------------------------------------------------------------------

@dataclass
class _Mapas:
    usuarios: dict[int, int]
    externos: dict[int, str]
    setores: dict[int, int]
    etiquetas: dict[int, tuple[str, int | str]]


def mapas_automaticos(sessao: Session, dados: dict[str, list[dict]]) -> "_Mapas":
    """O de-para sem revisão (migração pelo botão): as mesmas sugestões do `preparar`, aplicadas direto."""
    sug = _sugestoes(sessao, dados)
    linhas = lambda cab, rows: [dict(zip(cab, map(str, r))) for r in rows]
    return _mapas_de(sessao, linhas(["glpi_id", "login_glpi", "nome", "email", "login_sgi"], sug.usuarios),
                     linhas(["glpi_id", "grupo", "setor_sgi"], sug.grupos), linhas(["glpi_id", "etiqueta", "chamados", "acao"], sug.etiquetas))


def _mapas(sessao: Session, dados: dict[str, list[dict]], pasta: Path) -> _Mapas:
    return _mapas_de(sessao, _ler(pasta / "usuarios.csv"), _ler(pasta / "grupos.csv"), _ler(pasta / "etiquetas.csv"))


def _mapas_de(sessao: Session, linhas_usuarios: list[dict], linhas_grupos: list[dict], linhas_etiquetas: list[dict]) -> _Mapas:
    por_login = {u.login.lower(): u.id for u in sessao.scalars(select(Usuario))}
    setores = {s.nome.lower(): s.id for s in sessao.scalars(select(Setor))}
    usuarios, externos = {}, {}
    for linha in linhas_usuarios:
        glpi_id, login = int(linha["glpi_id"]), (linha.get("login_sgi") or "").strip().lower()
        if login:
            if login not in por_login:
                raise ErroImportacao(f"usuarios.csv: o login \"{login}\" não existe no SGI (linha do GLPI {glpi_id}).")
            usuarios[glpi_id] = por_login[login]
        else:
            externos[glpi_id] = (linha.get("email") or "").split(",")[0].strip() or (linha.get("nome") or linha.get("login_glpi") or "").strip()
    grupos = {}
    for linha in linhas_grupos:
        nome = (linha.get("setor_sgi") or "").strip().lower()
        if nome:
            if nome not in setores:
                raise ErroImportacao(f"grupos.csv: o setor \"{linha['setor_sgi']}\" não existe no SGI (grupo {linha['grupo']}).")
            grupos[int(linha["glpi_id"])] = setores[nome]
    etiquetas: dict[int, tuple[str, int | str]] = {}
    for linha in linhas_etiquetas:
        acao = (linha.get("acao") or "nota").strip()
        tipo, _, valor = acao.partition(":")
        tag = int(linha["glpi_id"])
        if tipo == "responsavel":
            if valor.strip().lower() not in por_login:
                raise ErroImportacao(f"etiquetas.csv: o login \"{valor}\" não existe no SGI (etiqueta {linha['etiqueta']}).")
            etiquetas[tag] = ("responsavel", por_login[valor.strip().lower()])
        elif tipo == "setor":
            if valor.strip().lower() not in setores:
                raise ErroImportacao(f"etiquetas.csv: o setor \"{valor}\" não existe no SGI (etiqueta {linha['etiqueta']}).")
            etiquetas[tag] = ("setor", setores[valor.strip().lower()])
        elif tipo in ("nota", ""):
            etiquetas[tag] = ("nota", linha["etiqueta"])
        elif tipo != "ignorar":
            raise ErroImportacao(f"etiquetas.csv: ação \"{acao}\" inválida (use responsavel:<login>, setor:<nome>, nota ou ignorar).")
    return _Mapas(usuarios, externos, grupos, etiquetas)


def _categorias_itil(sessao: Session, dados: dict[str, list[dict]], rel: Relatorio) -> dict[int, CategoriaItilChamados]:
    """Categorias do GLPI → **Categorias ITIL** (a classificação técnica), nunca assuntos. Pelo nível, para a mãe existir antes da filha.
    Já importada (mesmo `origem_glpi_id`): atualiza nome e mãe, que podem ter mudado no GLPI."""
    existentes = {c.origem_glpi_id: c for c in sessao.scalars(select(CategoriaItilChamados).where(CategoriaItilChamados.origem_glpi_id.is_not(None)))}
    usados: set[tuple] = {(c.pai_id, c.nome.lower()) for c in sessao.scalars(select(CategoriaItilChamados)) if c.origem_glpi_id is None}
    resultado: dict[int, CategoriaItilChamados] = {}
    for g in sorted(dados.get("glpi_itilcategories", []), key=lambda x: (x.get("level") or 1, x["id"])):
        rel.origem["categorias ITIL"] += 1
        pai = resultado.get(g.get("itilcategories_id") or 0)
        nome = str(g.get("name") or f"Categoria {g['id']}").replace(">", "-").strip()[:140]
        if (pai.id if pai else None, nome.lower()) in usados:
            rel.avisos.append(f"Categoria repetida no mesmo nível no GLPI: \"{nome}\" (id {g['id']}) virou \"{nome} (GLPI {g['id']})\"")
            nome = f"{nome} (GLPI {g['id']})"
        c = existentes.get(g["id"])
        if c is None:
            c = CategoriaItilChamados(id=uuid.uuid4(), origem_glpi_id=g["id"], ativa=True)
            sessao.add(c)
            rel.destino["categorias ITIL"] += 1
        else:
            rel.pulados["categorias ITIL"] += 1
        c.nome, c.pai, c.pai_id = nome, pai, pai.id if pai else None
        parametros._recalcular_caminho_itil(c)
        usados.add((c.pai_id, nome.lower()))
        resultado[g["id"]] = c
    sessao.flush()
    return resultado


ASSUNTO_IMPORTADOS = "Importados do GLPI"


def _assunto_importados(sessao: Session, setor_padrao: int) -> CategoriaChamados:
    """Assunto único dos chamados do GLPI (inativo: só guarda o histórico). A classificação deles fica na categoria ITIL."""
    c = sessao.scalar(select(CategoriaChamados).where(CategoriaChamados.pai_id.is_(None), func.lower(CategoriaChamados.nome) == ASSUNTO_IMPORTADOS.lower()))
    if c is None:
        c = CategoriaChamados(id=uuid.uuid4(), nome=ASSUNTO_IMPORTADOS, caminho=ASSUNTO_IMPORTADOS, nivel=1, setor_id=setor_padrao, ativa=False, visivel_solicitante=False)
        sessao.add(c)
        sessao.flush()
    return c


def _mudou_desde(t: dict, desde: datetime | None, filhos_recentes: set[int]) -> bool:
    """O chamado mudou no GLPI depois da última sincronização? (data de alteração dele ou de algum acompanhamento, solução, tarefa ou pesquisa)."""
    if desde is None:
        return True
    alterado = _data(t.get("date_mod"))
    return t["id"] in filhos_recentes or alterado is None or alterado >= desde


def _filhos_recentes(dados: dict[str, list[dict]], desde: datetime | None) -> set[int]:
    if desde is None:
        return set()
    recentes = set()
    for tabela, chave_ticket, chaves_data in (("glpi_itilfollowups", "items_id", ("date_mod", "date")), ("glpi_itilsolutions", "items_id", ("date_mod", "date_creation")),
                                               ("glpi_tickettasks", "tickets_id", ("date_mod", "date")), ("glpi_ticketvalidations", "tickets_id", ("validation_date", "submission_date")),
                                               ("glpi_ticketsatisfactions", "tickets_id", ("date_answered", "date_begin"))):
        for x in dados.get(tabela, []):
            if tabela in ("glpi_itilfollowups", "glpi_itilsolutions") and x.get("itemtype") != "Ticket":
                continue
            quando = max((d for d in (_data(x.get(k)) for k in chaves_data) if d), default=None)
            if quando and quando >= desde:
                recentes.add(x[chave_ticket])
    return recentes


def apagar_chamados(sessao: Session) -> int:
    """"Refazer do zero": apaga **todos** os chamados, os vindos do GLPI **e os abertos no próprio SGI** (decisão do usuário: a base volta a ser só
    o GLPI, para demonstração e treinamento), com o que pendura neles. Os arquivos anexos sofrem a exclusão lógica (ficam em disco para
    auditoria). Categorias, assuntos, SLAs e demais Parâmetros ficam; as categorias ITIL do GLPI são atualizadas pelo id de origem."""
    from sqlalchemy import delete, update

    from app.models.anexo import Anexo

    ids = list(sessao.scalars(select(Chamado.id)))
    if not ids:
        return 0
    for anexo in sessao.scalars(select(Anexo).where(Anexo.id.in_(select(AnexoChamado.anexo_id).where(AnexoChamado.chamado_id.in_(ids))))):
        servico_anexos.descartar(anexo)
    # Vínculos entre chamados (o "pai" trava a exclusão)
    sessao.execute(update(Chamado).values(relacionado_id=None, pai_id=None))
    for modelo in (AnexoChamado, AcompanhamentoChamado, SolucaoChamado, TarefaChamado, ValidacaoChamado, SatisfacaoChamado, AtorChamado):
        sessao.execute(delete(modelo).where(modelo.chamado_id.in_(ids)))
    sessao.execute(delete(Chamado).where(Chamado.id.in_(ids)))
    sessao.flush()
    return len(ids)


def carregar(sessao: Session, dados: dict[str, list[dict]], de_para: "Path | _Mapas", setor_padrao_id: int, arquivos: Path | None = None, *,
             atualizar: bool = False, desde: datetime | None = None, avisar=None, so_abertos: bool = False) -> Relatorio:
    """Carrega o histórico. Sem commit: quem chama grava ou desfaz.

    - `de_para`: a pasta com os CSVs revisados (script) ou os mapas já prontos (`mapas_automaticos`, botão de migração);
    - `atualizar`: o chamado que já veio e **mudou no GLPI** depois de `desde` (ou todos, sem `desde`) é regravado: campos e filhos vindos do GLPI
      (acompanhamentos, soluções, tarefas, aprovações, satisfação, cópias). Os ids dos acompanhamentos e soluções se mantêm (os anexos continuam
      apontando para eles). Sem `atualizar`, o que já veio é pulado, como sempre;
    - `avisar(etapa, mensagem, fracao)`: andamento para a tela;
    - `so_abertos`: não traz chamado **novo** que já está resolvido ou excluído no GLPI. O que já veio continua sendo atualizado (resolvido
      depois no GLPI fica resolvido aqui também, se ninguém mexeu nele no SGI).
    """
    sessao.info["sem_tempo_real"] = True
    avisar = avisar or (lambda *_: None)
    rel = Relatorio(versao=versao(dados))
    if sessao.get(Setor, setor_padrao_id) is None:
        raise ErroImportacao("Setor padrão não encontrado.")
    m = de_para if isinstance(de_para, _Mapas) else _mapas(sessao, dados, de_para)
    avisar("categorias", "Categorias do GLPI → categorias ITIL…", 0)
    itil = _categorias_itil(sessao, dados, rel)
    setor_da_categoria = {g["id"]: m.setores.get(g.get("groups_id") or 0) for g in dados.get("glpi_itilcategories", [])}
    assunto = _assunto_importados(sessao, setor_padrao_id)
    nomes_setor = {s.id: s.nome for s in sessao.scalars(select(Setor))}
    existentes = {c.origem_glpi_id: c for c in sessao.scalars(select(Chamado).where(Chamado.origem_glpi_id.is_not(None)))}
    numeros_ocupados = {n for (n,) in sessao.execute(select(Chamado.numero).where(Chamado.origem_glpi_id.is_(None)))}
    recentes = _filhos_recentes(dados, desde) if atualizar else set()

    # Atores, etiquetas e filhos agrupados por chamado
    usuarios_t, grupos_t = defaultdict(list), defaultdict(list)
    for x in dados.get("glpi_tickets_users", []):
        usuarios_t[x["tickets_id"]].append(x)
    for x in dados.get("glpi_groups_tickets", []):
        grupos_t[x["tickets_id"]].append(x)
    tags_t = defaultdict(list)
    for x in dados.get("glpi_plugin_tag_tagitems", []):
        if x.get("itemtype") == "Ticket":
            tags_t[x["items_id"]].append(x["plugin_tag_tags_id"])

    from sqlalchemy import delete

    criados: dict[int, Chamado] = {}
    # Ids antigos de acompanhamentos e soluções dos chamados regravados (os anexos apontam para eles)
    ids_antigos: dict[tuple[str, int], uuid.UUID] = {}
    tickets = sorted(dados.get("glpi_tickets", []), key=lambda x: x["id"])
    for n, t in enumerate(tickets, 1):
        rel.origem["chamados"] += 1
        if n % 25 == 0 or n == len(tickets):
            avisar("chamados", f"{n} de {len(tickets)} chamados do GLPI conferidos…", n / max(1, len(tickets)))
        antigo = existentes.get(t["id"])
        # Aberto que veio do GLPI e já foi trabalhado no SGI (assumido, respondido, alterado: a versão subiu): agora é daqui, não sobrescreve
        if antigo is not None and not antigo.importado and antigo.versao > 1:
            rel.pulados["trabalhados no SGI"] += 1
            continue
        if antigo is not None and not (atualizar and _mudou_desde(t, desde, recentes)):
            rel.pulados["chamados"] += 1
            continue
        if antigo is None and so_abertos and (STATUS.get(t.get("status") or 1) == STATUS_SOLUCIONADO or t.get("is_deleted")):
            rel.pulados["resolvidos no GLPI (não migrados)"] += 1
            continue
        if antigo is None and t["id"] in numeros_ocupados:
            rel.avisos.append(f"Chamado {t['id']} do GLPI não importado: o número já é de um chamado aberto no SGI.")
            continue
        requerentes = [m.usuarios.get(x["users_id"]) for x in usuarios_t[t["id"]] if x["type"] == REQUERENTE]
        externos = [m.externos.get(x["users_id"]) or x.get("alternative_email") for x in usuarios_t[t["id"]] if x["type"] == REQUERENTE]
        atribuidos = [m.usuarios[x["users_id"]] for x in usuarios_t[t["id"]] if x["type"] == ATRIBUIDO and x["users_id"] in m.usuarios]
        grupos_atr = [m.setores[x["groups_id"]] for x in grupos_t[t["id"]] if x["type"] == ATRIBUIDO and x["groups_id"] in m.setores]
        grupos_req = [m.setores[x["groups_id"]] for x in grupos_t[t["id"]] if x["type"] == REQUERENTE and x["groups_id"] in m.setores]
        notas = []
        for tag in tags_t[t["id"]]:
            acao = m.etiquetas.get(tag)
            if acao is None:
                continue
            if acao[0] == "responsavel" and acao[1] not in atribuidos:
                atribuidos.append(acao[1])
            elif acao[0] == "setor" and acao[1] not in grupos_atr:
                grupos_atr.append(acao[1])
            elif acao[0] == "nota":
                notas.append(str(acao[1]))
        solicitante = next((r for r in requerentes if r), None)
        externo = None if solicitante else next((e for e in externos if e), None) or f"Solicitante do GLPI (chamado {t['id']})"
        categoria_glpi = t.get("itilcategories_id") or 0
        setor_id = grupos_atr[0] if grupos_atr else setor_da_categoria.get(categoria_glpi) or setor_padrao_id
        status = STATUS.get(t.get("status") or 1, STATUS_NOVO)
        aberto = _data(t.get("date")) or _data(t.get("date_creation")) or datetime.now(UTC)
        campos = dict(
            # Resolvido no GLPI = histórico somente leitura; ainda aberto = chamado normal do SGI (painel, fila, assumir, responder, resolver)
            importado=status == STATUS_SOLUCIONADO, tipo="requisicao" if t.get("type") == 2 else "incidente",
            titulo=(str(t.get("name") or "").strip() or f"Chamado {t['id']} do GLPI")[:250], descricao=_texto(t.get("content")),
            status_base=status, prioridade=PRIORIDADE.get(t.get("priority") or 3, "normal"), prioridade_origem="importado",
            categoria_id=assunto.id, categoria_itil_id=itil[categoria_glpi].id if categoria_glpi in itil else None,
            setor_id=setor_id, setor_nome=nomes_setor.get(setor_id, ""), responsavel_id=atribuidos[0] if atribuidos else None,
            solicitante_id=solicitante, setor_solicitante_id=grupos_req[0] if grupos_req else None, solicitante_externo=externo[:254] if externo else None,
            aberto_em=aberto, prazo_tto=_data(t.get("time_to_own")), prazo_ttr=_data(t.get("time_to_resolve")),
            tomado_em=_data(t.get("takeintoaccountdate")), solucionado_em=_data(t.get("solvedate")) or _data(t.get("closedate")) if status == STATUS_SOLUCIONADO else None,
            excluido_em=(_data(t.get("date_mod")) or aberto) if t.get("is_deleted") else None,
        )
        if antigo is not None:
            # Regravar: os campos do GLPI por cima e os filhos refeitos (guarda os ids que os anexos usam)
            for a in sessao.scalars(select(AcompanhamentoChamado).where(AcompanhamentoChamado.chamado_id == antigo.id, AcompanhamentoChamado.origem_glpi_id.is_not(None))):
                ids_antigos[("ITILFollowup", a.origem_glpi_id)] = a.id
            for x in sessao.scalars(select(SolucaoChamado).where(SolucaoChamado.chamado_id == antigo.id, SolucaoChamado.origem_glpi_id.is_not(None))):
                ids_antigos[("ITILSolution", x.origem_glpi_id)] = x.id
            for modelo in (AcompanhamentoChamado, SolucaoChamado, TarefaChamado, ValidacaoChamado, SatisfacaoChamado, AtorChamado):
                sessao.execute(delete(modelo).where(modelo.chamado_id == antigo.id))
            sessao.expire(antigo)
            for k, v in campos.items():
                setattr(antigo, k, v)
            c = antigo
            rel.destino["chamados atualizados"] += 1
        else:
            c = Chamado(id=uuid.uuid4(), numero=t["id"], origem_glpi_id=t["id"], criado_em=aberto, **campos)
            sessao.add(c)
            rel.destino["chamados"] += 1
        criados[t["id"]] = c
        # Os demais atribuídos e os observadores ficam em cópia
        copia_u = set(atribuidos[1:]) | {m.usuarios[x["users_id"]] for x in usuarios_t[t["id"]] if x["type"] == OBSERVADOR and x["users_id"] in m.usuarios}
        copia_s = set(grupos_atr[1:]) | {m.setores[x["groups_id"]] for x in grupos_t[t["id"]] if x["type"] == OBSERVADOR and x["groups_id"] in m.setores}
        # Quem já é solicitante ou responsável não precisa estar em cópia
        copia_u -= {c.responsavel_id, c.solicitante_id}
        copia_s -= {c.setor_id, c.setor_solicitante_id}
        for u in copia_u:
            sessao.add(AtorChamado(chamado_id=c.id, usuario_id=u, criado_em=aberto))
        for s_ in copia_s:
            sessao.add(AtorChamado(chamado_id=c.id, setor_id=s_, criado_em=aberto))
        rel.destino["em cópia"] += len(copia_u) + len(copia_s)
        if notas:
            sessao.add(AcompanhamentoChamado(chamado_id=c.id, texto=f"<p>Etiquetas no GLPI: {html.escape(', '.join(notas))}</p>", automatico=True, privado=True,
                                             criado_em=aberto))
    sessao.flush()
    avisar("detalhes", "Acompanhamentos, soluções, tarefas, aprovações e satisfação…", 0)

    alvos: dict[tuple[str, int], tuple[str, uuid.UUID, uuid.UUID]] = {}
    for f in dados.get("glpi_itilfollowups", []):
        if f.get("itemtype") != "Ticket":
            continue
        rel.origem["acompanhamentos"] += 1
        c = criados.get(f["items_id"])
        if c is None:
            continue
        a = AcompanhamentoChamado(id=ids_antigos.get(("ITILFollowup", f["id"])) or uuid.uuid4(), chamado_id=c.id,
                                  autor_id=m.usuarios.get(f.get("users_id") or 0), texto=_texto(f.get("content")),
                                  privado=bool(f.get("is_private")), criado_em=_data(f.get("date")) or c.aberto_em, origem_glpi_id=f["id"])
        sessao.add(a)
        alvos[("ITILFollowup", f["id"])] = ("acompanhamento", c.id, a.id)
        rel.destino["acompanhamentos"] += 1

    solucoes = defaultdict(list)
    for s_ in dados.get("glpi_itilsolutions", []):
        if s_.get("itemtype") == "Ticket":
            rel.origem["soluções"] += 1
            solucoes[s_["items_id"]].append(s_)
    for ticket_id, lista in solucoes.items():
        c = criados.get(ticket_id)
        if c is None:
            continue
        lista.sort(key=lambda x: (str(x.get("date_creation") or ""), x["id"]))
        for i, s_ in enumerate(lista):
            # Só a última solução não recusada fica vigente; as anteriores (e as recusadas) ficam como substituídas
            vigente = i == len(lista) - 1 and s_.get("status") != 4 and c.status_base == STATUS_SOLUCIONADO
            x = SolucaoChamado(id=ids_antigos.get(("ITILSolution", s_["id"])) or uuid.uuid4(), chamado_id=c.id, autor_id=m.usuarios.get(s_.get("users_id") or 0),
                               texto=_texto(s_.get("content")), status="vigente" if vigente else "substituida",
                               criado_em=_data(s_.get("date_creation")) or c.aberto_em, origem_glpi_id=s_["id"])
            sessao.add(x)
            alvos[("ITILSolution", s_["id"])] = ("solucao", c.id, x.id)
            rel.destino["soluções"] += 1

    for t in dados.get("glpi_tickettasks", []):
        rel.origem["tarefas"] += 1
        c = criados.get(t["tickets_id"])
        if c is None:
            continue
        feita = t.get("state") in (0, 2)
        sessao.add(TarefaChamado(chamado_id=c.id, autor_id=m.usuarios.get(t.get("users_id") or 0), responsavel_id=m.usuarios.get(t.get("users_id_tech") or 0),
                                 texto=_texto(t.get("content")), estado="feita" if feita else "a_fazer", privada=bool(t.get("is_private", 1)),
                                 feita_em=(_data(t.get("end")) or _data(t.get("date_mod"))) if feita else None,
                                 criado_em=_data(t.get("date")) or c.aberto_em, origem_glpi_id=t["id"]))
        rel.destino["tarefas"] += 1

    nomes_glpi = {u["id"]: _nome_glpi(u) for u in dados.get("glpi_users", [])}
    nomes_grupo = {g["id"]: str(g.get("completename") or g.get("name") or "") for g in dados.get("glpi_groups", [])}
    for v in dados.get("glpi_ticketvalidations", []):
        rel.origem["aprovações"] += 1
        c = criados.get(v["tickets_id"])
        if c is None:
            continue
        alvo_u, alvo_s = None, None
        grupo = v.get("itemtype_target") == "Group"
        alvo_glpi = v.get("items_id_target") or v.get("users_id_validate") or 0
        if grupo:
            alvo_s = m.setores.get(alvo_glpi)
        else:
            alvo_u = m.usuarios.get(alvo_glpi)
        pedido = str(v.get("comment_submission") or "")
        if alvo_u is None and alvo_s is None:
            # Toda aprovação precisa de alvo (regra do banco): sem par no SGI, fica com o setor responsável e o texto guarda quem era no GLPI
            nome = (nomes_grupo if grupo else nomes_glpi).get(alvo_glpi) or f"{'grupo' if grupo else 'usuário'} {alvo_glpi} do GLPI"
            alvo_s = c.setor_id
            pedido = f"<p><em>Aprovador no GLPI: {html.escape(nome)} (sem par no SGI).</em></p>{pedido}"
            rel.avisos.append(f"Aprovação {v['id']} do chamado {v['tickets_id']}: aprovador \"{nome}\" sem par no SGI; ficou com o setor responsável.")
        estado = VALIDACAO.get(v.get("status") or 2, "aguardando")
        sessao.add(ValidacaoChamado(chamado_id=c.id, solicitante_id=m.usuarios.get(v.get("users_id") or 0), alvo_usuario_id=alvo_u, alvo_setor_id=alvo_s,
                                    status=estado, pedido=pedido, resposta=str(v.get("comment_validation") or ""),
                                    respondida_por_id=alvo_u if estado != "aguardando" else None, respondida_em=_data(v.get("validation_date")),
                                    criado_em=_data(v.get("submission_date")) or c.aberto_em, origem_glpi_id=v["id"]))
        rel.destino["aprovações"] += 1

    documentos = {d["id"]: d for d in dados.get("glpi_documents", [])}
    anexos_ja = {n for (n,) in sessao.execute(select(AnexoChamado.origem_glpi_id).where(AnexoChamado.origem_glpi_id.is_not(None)))}
    for di in dados.get("glpi_documents_items", []):
        tipo = di.get("itemtype")
        if tipo not in ("Ticket", "ITILFollowup", "ITILSolution"):
            continue
        rel.origem["anexos"] += 1
        if tipo == "Ticket":
            c = criados.get(di["items_id"])
            alvo = ("chamado", c.id, None) if c else None
        else:
            alvo = alvos.get((tipo, di["items_id"]))
        doc = documentos.get(di["documents_id"])
        if alvo is None or doc is None or doc.get("is_deleted") or di["id"] in anexos_ja:
            continue
        if arquivos is None:
            rel.pulados["anexos (sem a pasta files/)"] += 1
            continue
        caminho = arquivos / str(doc.get("filepath") or "")
        if not doc.get("filepath") or not caminho.is_file():
            rel.avisos.append(f"Anexo \"{doc.get('filename')}\" (documento {doc['id']}) não está na pasta files/.")
            continue
        anexo = servico_anexos.guardar_arquivo_gerado(sessao, caminho.read_bytes(), str(doc.get("filename") or caminho.name)[:255],
                                                     str(doc.get("mime") or "application/octet-stream"), CATEGORIA_ANEXO, m.usuarios.get(doc.get("users_id") or 0))
        sessao.add(AnexoChamado(chamado_id=alvo[1], anexo_id=anexo.id, alvo_tipo=alvo[0], alvo_id=alvo[2], origem_glpi_id=di["id"],
                                criado_em=_data(di.get("date_creation")) or datetime.now(UTC)))
        rel.destino["anexos"] += 1

    # Satisfação: a nota do GLPI (na escala de 5, quando a instalação usa outra) vira 1 a 5; zero ou vazio = pesquisa não respondida
    for x in dados.get("glpi_ticketsatisfactions", []):
        rel.origem["pesquisas de satisfação"] += 1
        c = criados.get(x["tickets_id"])
        if c is None:
            continue
        bruta = x.get("satisfaction_scaled_to_5") if x.get("satisfaction_scaled_to_5") is not None else x.get("satisfaction")
        nota = min(5, max(1, round(float(bruta)))) if bruta else None
        sessao.add(SatisfacaoChamado(chamado_id=c.id, nota=nota, comentario=str(x.get("comment") or "")[:2000], origem_glpi_id=x["id"],
                                     pedida_em=_data(x.get("date_begin")) or c.solucionado_em or c.aberto_em,
                                     respondida_em=_data(x.get("date_answered")) if nota else None))
        rel.destino["pesquisas de satisfação"] += 1
    sessao.flush()
    # Os números novos continuam depois do maior importado
    maior = sessao.scalar(select(func.max(Chamado.numero))) or 0
    if maior + 1 > parametros.obter_inteiro(sessao, "proximo_numero"):
        parametros.gravar(sessao, "proximo_numero", str(maior + 1))
    sessao.flush()
    return rel
