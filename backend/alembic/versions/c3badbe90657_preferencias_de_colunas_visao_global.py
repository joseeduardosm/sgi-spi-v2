# Criado por José Eduardo Santana Martins
# Este arquivo serve para permitir a visão global das colunas de uma listagem (preferência sem usuário, definida pelo administrador).
"""preferencias de colunas: visao global

Revision ID: c3badbe90657
Revises: 554e409aefd2
Create Date: 2026-10-12 02:20:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3badbe90657'
down_revision: Union[str, Sequence[str], None] = '554e409aefd2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """`usuario_id` nulo = visão global da tela; só uma por tela."""
    op.alter_column('usuarios_preferencias_colunas', 'usuario_id', existing_type=sa.Integer(), nullable=True)
    op.create_index('uq_usuarios_preferencias_colunas_global', 'usuarios_preferencias_colunas', ['tela'], unique=True, postgresql_where=sa.text('usuario_id IS NULL'))


def downgrade() -> None:
    """Remove as visões globais e volta a exigir o usuário."""
    op.drop_index('uq_usuarios_preferencias_colunas_global', table_name='usuarios_preferencias_colunas', postgresql_where=sa.text('usuario_id IS NULL'))
    op.execute("DELETE FROM usuarios_preferencias_colunas WHERE usuario_id IS NULL")
    op.alter_column('usuarios_preferencias_colunas', 'usuario_id', existing_type=sa.Integer(), nullable=False)
