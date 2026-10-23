# Criado por José Eduardo Santana Martins
# Este arquivo serve para permitir restringir o consumo dos números de um tipo de documento do Protocolo a um único setor.

"""protocolo: setor que pode consumir os números do tipo

Revision ID: c6d2e8f4a0b3
Revises: b5c1d7e3f9a2
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "c6d2e8f4a0b3"
down_revision: str | Sequence[str] | None = "b5c1d7e3f9a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Coluna opcional: nula = todos os usuários do Protocolo consomem o tipo (comportamento anterior)."""
    op.add_column("protocolo_tipos", sa.Column("setor_id", sa.Integer(), sa.ForeignKey("setores.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_protocolo_tipos_setor_id", "protocolo_tipos", ["setor_id"])


def downgrade() -> None:
    op.drop_index("ix_protocolo_tipos_setor_id", table_name="protocolo_tipos")
    op.drop_column("protocolo_tipos", "setor_id")
