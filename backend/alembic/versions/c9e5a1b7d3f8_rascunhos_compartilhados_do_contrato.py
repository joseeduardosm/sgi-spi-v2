# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela dos rascunhos compartilhados dos formulários do contrato (diário, avaliação e medição).
"""rascunhos compartilhados do contrato

Revision ID: c9e5a1b7d3f8
Revises: b8d4f0a6c2e3
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c9e5a1b7d3f8"
down_revision = "b8d4f0a6c2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contratos_rascunhos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("contrato_id", sa.Uuid(), sa.ForeignKey("contratos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("chave", sa.String(60), nullable=False, server_default=""),
        sa.Column("dados", postgresql.JSONB(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("atualizado_por_nome", sa.String(250), nullable=False),
        sa.UniqueConstraint("contrato_id", "tipo", "chave", name="uq_contratos_rascunhos_tela"),
        sa.CheckConstraint("tipo IN ('diario', 'avaliacao', 'medicao')", name="ck_contratos_rascunhos_tipo"),
    )
    op.create_index("ix_contratos_rascunhos_contrato_id", "contratos_rascunhos", ["contrato_id"])


def downgrade() -> None:
    op.drop_index("ix_contratos_rascunhos_contrato_id", table_name="contratos_rascunhos")
    op.drop_table("contratos_rascunhos")
