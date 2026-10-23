# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar na admissão a foto da pessoa (enviada ao GLPI e à intranet).

"""rh: foto da admissão

Revision ID: f3a9e5b1d7c0
Revises: e2f8d4a0c6b9
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f3a9e5b1d7c0"
down_revision: str | Sequence[str] | None = "e2f8d4a0c6b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rh_admissoes", sa.Column("foto_anexo_id", sa.Uuid(), sa.ForeignKey("anexos.id", ondelete="SET NULL")))


def downgrade() -> None:
    with op.batch_alter_table("rh_admissoes") as lote:
        lote.drop_column("foto_anexo_id")
