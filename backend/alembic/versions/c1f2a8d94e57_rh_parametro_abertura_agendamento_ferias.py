# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar a data de abertura do agendamento das férias do ano seguinte (parâmetro do RH).
"""rh: data de abertura do agendamento das férias do próximo exercício

Revision ID: c1f2a8d94e57
Revises: b8e41f6a2c93
Create Date: 2026-10-01 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1f2a8d94e57'
down_revision: Union[str, Sequence[str], None] = 'b8e41f6a2c93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rh_parametros', sa.Column('abertura_agendamento_ferias', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rh_parametros', 'abertura_agendamento_ferias')
