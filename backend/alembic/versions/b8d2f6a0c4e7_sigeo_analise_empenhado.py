# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar o caminho da análise de empenhos do SIGEO, usada para cadastrar sozinha as NEs dos contratos.

"""sigeo: caminho da análise das Notas de Empenho emitidas

Revision ID: b8d2f6a0c4e7
Revises: d4f8b2c6a0e3
Create Date: 2026-10-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b8d2f6a0c4e7"
down_revision: str | Sequence[str] | None = "d4f8b2c6a0e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PADRAO = "/users/31818707810/SPI - Execução/EMPENHADO - Execução"


def upgrade() -> None:
    op.add_column("integracao_sigeo", sa.Column("caminho_analise_empenhado", sa.String(length=500), nullable=False, server_default=PADRAO))


def downgrade() -> None:
    op.drop_column("integracao_sigeo", "caminho_analise_empenhado")
