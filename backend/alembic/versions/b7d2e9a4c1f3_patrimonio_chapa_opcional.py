# Criado por José Eduardo Santana Martins
# Este arquivo serve para tornar a chapa do bem opcional (ativos importados do GLPI sem patrimônio só têm o número de série).
"""patrimonio: chapa opcional

Revision ID: b7d2e9a4c1f3
Revises: a1c4e7b9d2f6
Create Date: 2026-10-12 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7d2e9a4c1f3'
down_revision: Union[str, Sequence[str], None] = 'a1c4e7b9d2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """A chapa e a chave dela aceitam nulo; a unicidade continua valendo para as preenchidas."""
    op.alter_column('patrimonio_bens', 'chapa', existing_type=sa.String(length=60), nullable=True)
    op.alter_column('patrimonio_bens', 'chapa_chave', existing_type=sa.String(length=60), nullable=True)


def downgrade() -> None:
    """Volta a exigir chapa: bens sem chapa recebem o número de série (ou o id) para não perder o registro."""
    op.execute("UPDATE patrimonio_bens SET chapa = COALESCE(numero_serie, 'SEM-' || substr(id::text, 1, 8)) WHERE chapa IS NULL")
    op.execute("UPDATE patrimonio_bens SET chapa_chave = lower(chapa) WHERE chapa_chave IS NULL")
    op.alter_column('patrimonio_bens', 'chapa_chave', existing_type=sa.String(length=60), nullable=False)
    op.alter_column('patrimonio_bens', 'chapa', existing_type=sa.String(length=60), nullable=False)
