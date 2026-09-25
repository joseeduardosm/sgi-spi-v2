"""Cálculo do nível de acesso efetivo (ACL).

Política:
- SuperRoot sempre tem CONTROLE_TOTAL.
- Recurso não cadastrado, inativo ou sem regras: aberto (CONTROLE_TOTAL para autenticados).
- Com ao menos uma regra, o recurso vira lista positiva: só usuários ou setores contemplados.
- Regra direta (usuário) prevalece sobre herança por setor; entre várias, vale o maior nível.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.acl import NivelAcl, RecursoAcl, RegraAcl, acl_regras_setores, acl_regras_usuarios
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario


def _maior_nivel(niveis: list[str]) -> str | None:
    return max(niveis, key=NivelAcl.posicao) if niveis else None


def resolver_acesso(sessao: Session, usuario: Usuario, slug: str) -> str | None:
    if usuario.superusuario:
        return NivelAcl.CONTROLE_TOTAL
    recurso = sessao.scalar(
        select(RecursoAcl).where(func.lower(RecursoAcl.slug) == slug.lower(), RecursoAcl.ativo.is_(True))
    )
    if recurso is None:
        return NivelAcl.CONTROLE_TOTAL
    return _resolver_no_recurso(sessao, usuario.id, recurso.id)


def _resolver_no_recurso(sessao: Session, usuario_id: int, recurso_id: int) -> str | None:
    possui_regras = sessao.scalar(select(func.count(RegraAcl.id)).where(RegraAcl.recurso_id == recurso_id))
    if not possui_regras:
        return NivelAcl.CONTROLE_TOTAL

    diretos = list(
        sessao.scalars(
            select(RegraAcl.nivel)
            .join(acl_regras_usuarios, acl_regras_usuarios.c.regra_id == RegraAcl.id)
            .where(RegraAcl.recurso_id == recurso_id, acl_regras_usuarios.c.usuario_id == usuario_id)
        )
    )
    if diretos:
        return _maior_nivel(diretos)

    herdados = list(
        sessao.scalars(
            select(RegraAcl.nivel)
            .join(acl_regras_setores, acl_regras_setores.c.regra_id == RegraAcl.id)
            .join(MembroSetor, MembroSetor.setor_id == acl_regras_setores.c.setor_id)
            .join(Setor, Setor.id == MembroSetor.setor_id)
            .where(RegraAcl.recurso_id == recurso_id, MembroSetor.usuario_id == usuario_id, Setor.ativo.is_(True))
        )
    )
    return _maior_nivel(herdados)


def acessos_efetivos(sessao: Session, usuario: Usuario) -> list[tuple[RecursoAcl, str | None]]:
    """Nível efetivo do usuário em cada recurso ativo (None = sem acesso)."""
    recursos = sessao.scalars(select(RecursoAcl).where(RecursoAcl.ativo.is_(True)).order_by(func.lower(RecursoAcl.nome)))
    return [
        (r, NivelAcl.CONTROLE_TOTAL if usuario.superusuario else _resolver_no_recurso(sessao, usuario.id, r.id))
        for r in recursos
    ]
