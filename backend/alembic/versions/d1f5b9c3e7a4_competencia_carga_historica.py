# Criado por José Eduardo Santana Martins
# Este arquivo serve para marcar nas competências as que foram lançadas por carga histórica (depois de pagas, sem o limite mensal de quantidades).

"""contratos: marca de carga histórica na competência

Revision ID: d1f5b9c3e7a4
Revises: c9e3a7f1b5d2
Create Date: 2026-10-27
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d1f5b9c3e7a4"
down_revision: str | Sequence[str] | None = "c9e3a7f1b5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contratos_competencias", sa.Column("carga_historica_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contratos_competencias", sa.Column("carga_historica_obs", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("contratos_competencias", "carga_historica_obs")
    op.drop_column("contratos_competencias", "carga_historica_em")
