# Criado por José Eduardo Santana Martins
# Este arquivo serve para ampliar o nome do marcador de tarefas para 120 caracteres.
"""tarefas_marcadores.nome: 60 → 120 caracteres (marcadores migrados do 10.23.1.220 têm até 78)

Revision ID: 9639d1d834db
Revises: 2320f1538b36
Create Date: 2026-09-29 22:50:24.926864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9639d1d834db'
down_revision: Union[str, Sequence[str], None] = '2320f1538b36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('tarefas_marcadores', 'nome',
               existing_type=sa.VARCHAR(length=60),
               type_=sa.String(length=120),
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('tarefas_marcadores', 'nome',
               existing_type=sa.String(length=120),
               type_=sa.VARCHAR(length=60),
               existing_nullable=False)
