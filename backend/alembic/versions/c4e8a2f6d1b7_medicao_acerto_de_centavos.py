# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a coluna "acerto" nos itens da medição (centavos de dízimas e arredondamentos).
"""contratos: acerto de centavos por item da medição

`contratos_competencias_itens.acerto` (R$, 2 casas, padrão 0): o usuário lança +0,01, -0,02... em cada item medido; soma ao valor do item e ao total
medido. Competências existentes ficam com 0 e os totais não mudam.

Revision ID: c4e8a2f6d1b7
Revises: b3d9f5a7c2e1
Create Date: 2026-10-13 22:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4e8a2f6d1b7'
down_revision: Union[str, Sequence[str], None] = 'b3d9f5a7c2e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('contratos_competencias_itens', sa.Column('acerto', sa.Numeric(18, 2), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('contratos_competencias_itens', 'acerto')
