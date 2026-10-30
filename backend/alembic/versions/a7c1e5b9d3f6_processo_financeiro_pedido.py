# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar no contrato quem pediu o processo financeiro ao DOF e quando (legenda do campo).

"""contratos: último pedido do processo financeiro ao DOF (quem e quando)

Revision ID: a7c1e5b9d3f6
Revises: f6b0d4a8c2e5
Create Date: 2026-10-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a7c1e5b9d3f6"
down_revision: str | Sequence[str] | None = "f6b0d4a8c2e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contratos", sa.Column("processo_financeiro_pedido_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contratos", sa.Column("processo_financeiro_pedido_por", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("contratos", "processo_financeiro_pedido_por")
    op.drop_column("contratos", "processo_financeiro_pedido_em")
