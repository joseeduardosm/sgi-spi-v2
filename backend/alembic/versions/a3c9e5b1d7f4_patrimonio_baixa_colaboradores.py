# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela dos colaboradores com quem uma baixa de bens é compartilhada.
"""patrimônio: colaboradores da baixa

Revision ID: a3c9e5b1d7f4
Revises: f2b8d4c0a6e1
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "a3c9e5b1d7f4"
down_revision = "f2b8d4c0a6e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patrimonio_baixa_colaboradores",
        sa.Column("baixa_id", sa.Uuid(), sa.ForeignKey("patrimonio_baixas.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("adicionado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_patrimonio_baixa_colaboradores_usuario_id", "patrimonio_baixa_colaboradores", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_patrimonio_baixa_colaboradores_usuario_id", table_name="patrimonio_baixa_colaboradores")
    op.drop_table("patrimonio_baixa_colaboradores")
