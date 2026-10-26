# Criado por José Eduardo Santana Martins
# Este arquivo serve para tornar parametrizável a hora da conferência diária das OBs no SIGEO.

"""sigeo: hora da conferência diária (padrão 8)

Revision ID: f6b0d4a8c2e5
Revises: e5a9c3f7b1d4
Create Date: 2026-10-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f6b0d4a8c2e5"
down_revision: str | Sequence[str] | None = "e5a9c3f7b1d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("integracao_sigeo", sa.Column("hora_conferencia", sa.Integer(), nullable=False, server_default="8"))


def downgrade() -> None:
    op.drop_column("integracao_sigeo", "hora_conferencia")
