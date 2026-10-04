# Criado por José Eduardo Santana Martins
# Este arquivo serve para acrescentar a coluna `linkedin` (link do perfil) na tabela de usuários.
"""usuarios_linkedin

Revision ID: 7c1e9a3b5d20
Revises: 44f539651816
Create Date: 2026-10-03 22:50:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '7c1e9a3b5d20'
down_revision: Union[str, Sequence[str], None] = '44f539651816'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('usuarios', sa.Column('linkedin', sa.String(length=200), server_default='', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('usuarios', 'linkedin')
