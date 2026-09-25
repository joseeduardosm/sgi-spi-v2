# Criado por José Eduardo Santana Martins
# Este arquivo serve para administrar recursos e regras de ACL.
"""Administração de recursos e regras de ACL (SuperRoot)."""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.acl import RecursoAcl, RegraAcl
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.schemas.acl import GravacaoRecurso, GravacaoRegra, LeituraRecurso, LeituraRegra, OpcaoSetor
from app.services.servico_admin_usuarios import para_opcao
from app.services.servico_auditoria import auditar


class AclNaoEncontrado(Exception):
    pass


class ErroRegraAcl(Exception):
    def __init__(self, mensagem: str, conflito: bool = False) -> None:
        super().__init__(mensagem)
        self.conflito = conflito


def normalizar_slug(valor: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", valor.strip().lower()).strip("-")


# --- Recursos -------------------------------------------------------------------

def listar_recursos(sessao: Session) -> list[LeituraRecurso]:
    totais = dict(sessao.execute(select(RegraAcl.recurso_id, func.count()).group_by(RegraAcl.recurso_id)).all())
    return [
        LeituraRecurso(
            id=r.id,
            nome=r.nome,
            slug=r.slug,
            descricao=r.descricao,
            url_base=r.url_base,
            ativo=r.ativo,
            total_regras=totais.get(r.id, 0),
            criado_em=r.criado_em,
            atualizado_em=r.atualizado_em,
        )
        for r in sessao.scalars(select(RecursoAcl).order_by(func.lower(RecursoAcl.nome)))
    ]


def ler_recurso(sessao: Session, recurso_id: int) -> LeituraRecurso:
    return next(r for r in listar_recursos(sessao) if r.id == recurso_id)


def obter_recurso(sessao: Session, recurso_id: int) -> RecursoAcl:
    recurso = sessao.get(RecursoAcl, recurso_id)
    if recurso is None:
        raise AclNaoEncontrado()
    return recurso


def gravar_recurso(sessao: Session, dados: GravacaoRecurso, autor: str, recurso_id: int | None = None) -> RecursoAcl:
    slug = normalizar_slug(dados.slug)
    if not dados.nome or not slug:
        raise ErroRegraAcl("Nome e slug são obrigatórios.")
    conflitante = sessao.scalar(
        select(RecursoAcl.id).where(
            (func.lower(RecursoAcl.nome) == dados.nome.lower()) | (RecursoAcl.slug == slug),
            RecursoAcl.id != (recurso_id or 0),
        )
    )
    if conflitante is not None:
        raise ErroRegraAcl("Nome e slug do recurso devem ser únicos.", conflito=True)
    recurso = obter_recurso(sessao, recurso_id) if recurso_id else RecursoAcl()
    recurso.nome, recurso.slug, recurso.descricao = dados.nome, slug, dados.descricao
    recurso.url_base, recurso.ativo = dados.url_base, dados.ativo
    if recurso_id is None:
        sessao.add(recurso)
    sessao.flush()
    auditar(sessao, autor, "acl.recurso.alterar" if recurso_id else "acl.recurso.criar", recurso.slug, f"ativo={recurso.ativo}")
    sessao.commit()
    return recurso


def excluir_recurso(sessao: Session, recurso_id: int, autor: str) -> None:
    recurso = obter_recurso(sessao, recurso_id)
    auditar(sessao, autor, "acl.recurso.excluir", recurso.slug)
    sessao.delete(recurso)  # regras removidas em cascata
    sessao.commit()


# --- Regras ---------------------------------------------------------------------

def para_leitura_regra(regra: RegraAcl) -> LeituraRegra:
    return LeituraRegra(
        id=regra.id,
        recurso_id=regra.recurso_id,
        recurso_nome=regra.recurso.nome,
        recurso_slug=regra.recurso.slug,
        nivel=regra.nivel,
        usuarios=[para_opcao(u) for u in regra.usuarios],
        setores=[OpcaoSetor(id=s.id, nome=s.nome, sistemico=s.sistemico) for s in regra.setores],
        criado_em=regra.criado_em,
        atualizado_em=regra.atualizado_em,
    )


def listar_regras(sessao: Session, recurso_id: int | None = None) -> list[LeituraRegra]:
    consulta = select(RegraAcl).join(RecursoAcl).order_by(func.lower(RecursoAcl.nome), RegraAcl.id)
    if recurso_id is not None:
        consulta = consulta.where(RegraAcl.recurso_id == recurso_id)
    return [para_leitura_regra(r) for r in sessao.scalars(consulta).unique()]


def obter_regra(sessao: Session, regra_id: int) -> RegraAcl:
    regra = sessao.get(RegraAcl, regra_id)
    if regra is None:
        raise AclNaoEncontrado()
    return regra


def gravar_regra(sessao: Session, dados: GravacaoRegra, autor: str, regra_id: int | None = None) -> RegraAcl:
    if sessao.get(RecursoAcl, dados.recurso_id) is None:
        raise ErroRegraAcl("Recurso inválido.")
    usuarios_ids, setores_ids = sorted(set(dados.usuarios_ids)), sorted(set(dados.setores_ids))
    if not usuarios_ids and not setores_ids:
        raise ErroRegraAcl("Selecione ao menos um usuário ou setor.")
    usuarios = list(sessao.scalars(select(Usuario).where(Usuario.id.in_(usuarios_ids)))) if usuarios_ids else []
    setores = list(sessao.scalars(select(Setor).where(Setor.id.in_(setores_ids)))) if setores_ids else []
    if len(usuarios) != len(usuarios_ids) or len(setores) != len(setores_ids):
        raise ErroRegraAcl("A regra contém usuários ou setores inválidos.")
    regra = obter_regra(sessao, regra_id) if regra_id else RegraAcl()
    regra.recurso_id, regra.nivel = dados.recurso_id, dados.nivel
    regra.usuarios, regra.setores = usuarios, setores
    if regra_id is None:
        sessao.add(regra)
    sessao.flush()
    auditar(
        sessao, autor, "acl.regra.alterar" if regra_id else "acl.regra.criar", f"regra {regra.id}",
        f"recurso={dados.recurso_id} nivel={dados.nivel} usuarios={usuarios_ids} setores={setores_ids}",
    )
    sessao.commit()
    sessao.refresh(regra)
    return regra


def excluir_regra(sessao: Session, regra_id: int, autor: str) -> None:
    regra = obter_regra(sessao, regra_id)
    auditar(sessao, autor, "acl.regra.excluir", f"regra {regra.id}", f"recurso={regra.recurso_id} nivel={regra.nivel}")
    sessao.delete(regra)
    sessao.commit()
