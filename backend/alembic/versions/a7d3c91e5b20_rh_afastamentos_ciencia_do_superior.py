# Criado por José Eduardo Santana Martins
# Este arquivo serve para registrar o "ciente e de acordo" do superior imediato (etapa 1) nos pedidos de férias e licença-prêmio.
"""rh: ciente e de acordo do superior imediato nos afastamentos

Acrescenta `aguarda_ciencia` (padrão falso, então os pedidos existentes seguem como estão) e quem/quando deu o ciente.

Revision ID: a7d3c91e5b20
Revises: 78fca44765aa
Create Date: 2026-10-01 20:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d3c91e5b20'
down_revision: Union[str, Sequence[str], None] = '78fca44765aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rh_afastamentos', sa.Column('aguarda_ciencia', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('rh_afastamentos', sa.Column('ciencia_por_id', sa.Integer(), nullable=True))
    op.add_column('rh_afastamentos', sa.Column('ciencia_por_nome', sa.String(length=200), nullable=True))
    op.add_column('rh_afastamentos', sa.Column('ciencia_em', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('rh_afastamentos_ciencia_por_id_fkey', 'rh_afastamentos', 'usuarios', ['ciencia_por_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('rh_afastamentos_ciencia_por_id_fkey', 'rh_afastamentos', type_='foreignkey')
    op.drop_column('rh_afastamentos', 'ciencia_em')
    op.drop_column('rh_afastamentos', 'ciencia_por_nome')
    op.drop_column('rh_afastamentos', 'ciencia_por_id')
    op.drop_column('rh_afastamentos', 'aguarda_ciencia')
