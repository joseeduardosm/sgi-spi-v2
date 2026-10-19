# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela que liga os perfis de acesso a setores e grupos sistêmicos.
"""perfis de acesso por setor ou grupo sistêmico

Revision ID: c5e1a7d3f9b6
Revises: b4d0f6c2e8a5
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "c5e1a7d3f9b6"
down_revision = "b4d0f6c2e8a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "acl_perfis_setores",
        sa.Column("perfil_id", sa.Integer(), sa.ForeignKey("acl_perfis.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("setor_id", sa.Integer(), sa.ForeignKey("setores.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_acl_perfis_setores_setor_id", "acl_perfis_setores", ["setor_id"])


def downgrade() -> None:
    op.drop_index("ix_acl_perfis_setores_setor_id", table_name="acl_perfis_setores")
    op.drop_table("acl_perfis_setores")
