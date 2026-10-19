# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a coluna que marca as contas de integração (dispensadas de confirmar o cadastro todo mês).
"""usuários: conta de integração

`usuarios.conta_integracao`: conta usada por outro sistema (ex.: lançar a OB pela API). Não tem pessoa para completar e confirmar o cadastro
todo mês, então fica dispensada disso (só disso).

Revision ID: d0f6b2c8e4a9
Revises: c9e5a1b7d3f8
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

revision = "d0f6b2c8e4a9"
down_revision = "c9e5a1b7d3f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("conta_integracao", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("usuarios", "conta_integracao")
