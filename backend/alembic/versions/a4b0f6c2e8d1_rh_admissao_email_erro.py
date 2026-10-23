# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar o motivo da falha do envio automático do e-mail de nomeação.

"""rh: motivo da falha do e-mail automático de nomeação

Revision ID: a4b0f6c2e8d1
Revises: f3a9e5b1d7c0
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a4b0f6c2e8d1"
down_revision: str | Sequence[str] | None = "f3a9e5b1d7c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rh_admissoes", sa.Column("email_erro", sa.String(500)))


def downgrade() -> None:
    with op.batch_alter_table("rh_admissoes") as lote:
        lote.drop_column("email_erro")
