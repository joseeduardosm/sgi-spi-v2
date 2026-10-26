# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela das curtidas nos cartões de contato do Diretório de ramais.

"""diretório: curtidas nos cartões de contato

Revision ID: c3e7a1f5b9d2
Revises: b2d6f0a4c8e1
Create Date: 2026-10-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "c3e7a1f5b9d2"
down_revision: str | Sequence[str] | None = "b2d6f0a4c8e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diretorio_curtidas",
        sa.Column("contato_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("diretorio_curtidas")
