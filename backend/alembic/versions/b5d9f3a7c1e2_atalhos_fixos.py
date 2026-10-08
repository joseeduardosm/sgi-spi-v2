# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas dos atalhos fixos da barra lateral e o recurso de ACL "atalhos" (gestão fechada).
"""atalhos fixos: categorias, atalhos e recurso de ACL `atalhos`

Todos os usuários veem os atalhos ativos; criar, alterar e excluir exige o recurso `atalhos` ≥ MODIFICACAO (ou SuperRoot). O recurso nasce
**fechado**: uma regra CONTROLE_TOTAL só para a conta administrativa principal (LOGIN_ADMIN; na falta dela, os superusuários), e o SuperRoot
libera depois os demais na tela de Controle de acesso.

Revision ID: b5d9f3a7c1e2
Revises: a4c8e2f6b0d1
Create Date: 2026-10-06 11:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.core.configuracao import obter_configuracao

# Identificação da migração: esta revisão e a anterior
revision: str = "b5d9f3a7c1e2"
down_revision: str | Sequence[str] | None = "a4c8e2f6b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "atalhos"


def upgrade() -> None:
    """Cria as tabelas e o recurso de ACL fechado."""
    op.create_table(
        "atalhos_categorias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=80), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ux_atalhos_categorias_nome", "atalhos_categorias", [sa.text("lower(nome)")], unique=True)
    op.create_table(
        "atalhos_fixos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("categoria_id", sa.Integer(), sa.ForeignKey("atalhos_categorias.id", ondelete="CASCADE"), nullable=False),
        sa.Column("titulo", sa.String(length=80), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("nova_aba", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_atalhos_fixos_categoria_id", "atalhos_fixos", ["categoria_id"])

    conexao = op.get_bind()
    agora = datetime.now(UTC)
    recurso_id = conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :slug"), {"slug": SLUG})
    if recurso_id is None:
        recurso_id = conexao.scalar(
            sa.text(
                "INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES (:nome, :slug, :descricao, '/admin/atalhos', true, :agora, :agora) RETURNING id"
            ),
            {"nome": "Atalhos (gestão)", "slug": SLUG, "agora": agora,
             "descricao": "Cadastro das categorias e dos atalhos fixos da barra lateral (todos os usuários veem; só quem tem MODIFICACAO gerencia)."},
        )
    if conexao.scalar(sa.text("SELECT count(*) FROM acl_regras WHERE recurso_id = :id"), {"id": recurso_id}):
        return
    usuarios = conexao.scalars(
        sa.text("SELECT id FROM usuarios WHERE lower(login) = lower(:login)"), {"login": obter_configuracao().login_admin}
    ).all() or conexao.scalars(sa.text("SELECT id FROM usuarios WHERE superusuario")).all()
    if not usuarios:
        return
    regra_id = conexao.scalar(
        sa.text("INSERT INTO acl_regras (recurso_id, nivel, criado_em, atualizado_em) VALUES (:id, 'CONTROLE_TOTAL', :agora, :agora) RETURNING id"),
        {"id": recurso_id, "agora": agora},
    )
    for usuario_id in usuarios:
        conexao.execute(sa.text("INSERT INTO acl_regras_usuarios (regra_id, usuario_id) VALUES (:regra, :usuario)"), {"regra": regra_id, "usuario": usuario_id})


def downgrade() -> None:
    """Remove as tabelas e o recurso de ACL."""
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :slug").bindparams(slug=SLUG))
    op.drop_index("ix_atalhos_fixos_categoria_id", table_name="atalhos_fixos")
    op.drop_table("atalhos_fixos")
    op.drop_index("ux_atalhos_categorias_nome", table_name="atalhos_categorias")
    op.drop_table("atalhos_categorias")
