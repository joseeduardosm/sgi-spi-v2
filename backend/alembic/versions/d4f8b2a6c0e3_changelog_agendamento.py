# Criado por José Eduardo Santana Martins
# Este arquivo serve para acrescentar o agendamento aos e-mails de changelog (quando sai, início, cancelamento e a seleção guardada).

"""notificações: e-mail de changelog agendado

Revision ID: d4f8b2a6c0e3
Revises: c3e7a1f5b9d2
Create Date: 2026-10-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d4f8b2a6c0e3"
down_revision: str | Sequence[str] | None = "c3e7a1f5b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELA = "notificacoes_envios_changelog"


def upgrade() -> None:
    op.add_column(TABELA, sa.Column("agendado_para", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABELA, sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABELA, sa.Column("cancelado_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABELA, sa.Column("selecao", sa.JSON(), nullable=True))
    # Os envios que já existem saíram na hora: começaram quando foram criados
    op.execute(sa.text(f"UPDATE {TABELA} SET iniciado_em = criado_em"))


def downgrade() -> None:
    for coluna in ("selecao", "cancelado_em", "iniciado_em", "agendado_para"):
        op.drop_column(TABELA, coluna)
