# Criado por José Eduardo Santana Martins
# Este arquivo serve para acrescentar o campo "liberar a partir de" às sequências do Protocolo (faixa reservada ao Serviço de Apoio Administrativo).
"""protocolo: faixa reservada ao SAA (liberar a partir de)

Revision ID: f8b3c5d7e9a1
Revises: e7a2b4d6f8c1
Create Date: 2026-10-09 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f8b3c5d7e9a1"
down_revision: str | Sequence[str] | None = "e7a2b4d6f8c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Coluna opcional: as sequências existentes continuam sem faixa reservada."""
    op.add_column("protocolo_sequencias", sa.Column("liberar_a_partir_de", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_protocolo_sequencias_liberar", "protocolo_sequencias",
        "liberar_a_partir_de IS NULL OR (liberar_a_partir_de >= inicio AND liberar_a_partir_de <= fim + 1)")


def downgrade() -> None:
    op.drop_constraint("ck_protocolo_sequencias_liberar", "protocolo_sequencias", type_="check")
    op.drop_column("protocolo_sequencias", "liberar_a_partir_de")
