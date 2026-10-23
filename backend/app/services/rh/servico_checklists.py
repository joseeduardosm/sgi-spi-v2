# Criado por José Eduardo Santana Martins
# Este arquivo serve para cadastrar os checklists de documentos da admissão, por tipo de cargo.
"""Checklists do RH: lista de documentos exigidos, ligada a uma ou mais classificações de cargo (grupo + nível, ex.: 1.15, 1.16) e, se quiser, aos cargos sem classificação."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rh_admissao import ChecklistClassificacao, ChecklistRh, ItemChecklistRh
from app.models.usuario import Usuario
from app.schemas.rh_admissao import GravacaoChecklist, LeituraChecklist
from app.services.servico_auditoria import auditar


class ChecklistNaoEncontrado(Exception):
    """Checklist inexistente (vira 404)."""


class ErroChecklist(Exception):
    """Dados inválidos (vira 400)."""


def leitura(sessao: Session, lista: ChecklistRh) -> LeituraChecklist:
    return LeituraChecklist(id=lista.id, nome=lista.nome, ativo=lista.ativo, aplica_a_outros=lista.aplica_a_outros,
                            classificacoes=[{"grupo": c.grupo, "nivel": c.nivel} for c in lista.classificacoes],
                            itens=[{"descricao": i.descricao, "obrigatorio": i.obrigatorio} for i in lista.itens])


def listar(sessao: Session) -> list[LeituraChecklist]:
    return [leitura(sessao, c) for c in sessao.scalars(select(ChecklistRh).order_by(ChecklistRh.nome))]


def _aplicar(sessao: Session, lista: ChecklistRh, dados: GravacaoChecklist) -> None:
    if not dados.classificacoes and not dados.aplica_a_outros:
        raise ErroChecklist("Escolha ao menos uma classificação de cargo (grupo e nível) ou marque os cargos sem classificação.")
    descricoes = [i.descricao.strip().lower() for i in dados.itens]
    if len(set(descricoes)) != len(descricoes):
        raise ErroChecklist("Há documentos repetidos na lista.")
    lista.nome, lista.ativo, lista.aplica_a_outros = dados.nome.strip(), dados.ativo, dados.aplica_a_outros
    unicas = dict.fromkeys((c.grupo, c.nivel) for c in dados.classificacoes)
    lista.classificacoes = [ChecklistClassificacao(grupo=g, nivel=n) for g, n in unicas]
    lista.itens = [ItemChecklistRh(descricao=i.descricao.strip(), obrigatorio=i.obrigatorio, ordem=n) for n, i in enumerate(dados.itens)]


def criar(sessao: Session, dados: GravacaoChecklist, autor: Usuario) -> LeituraChecklist:
    lista = ChecklistRh()
    _aplicar(sessao, lista, dados)
    sessao.add(lista)
    sessao.flush()
    auditar(sessao, autor.login, "rh.checklist.criar", lista.nome, autor_id=autor.id)
    sessao.commit()
    return leitura(sessao, lista)


def alterar(sessao: Session, checklist_id: int, dados: GravacaoChecklist, autor: Usuario) -> LeituraChecklist:
    lista = sessao.get(ChecklistRh, checklist_id)
    if lista is None:
        raise ChecklistNaoEncontrado()
    _aplicar(sessao, lista, dados)
    auditar(sessao, autor.login, "rh.checklist.alterar", lista.nome, autor_id=autor.id)
    sessao.commit()
    return leitura(sessao, lista)


def excluir(sessao: Session, checklist_id: int, autor: Usuario) -> None:
    """Admissões já iniciadas guardam a própria cópia dos itens: excluir a lista não as afeta."""
    lista = sessao.get(ChecklistRh, checklist_id)
    if lista is None:
        raise ChecklistNaoEncontrado()
    auditar(sessao, autor.login, "rh.checklist.excluir", lista.nome, autor_id=autor.id)
    sessao.delete(lista)
    sessao.commit()
