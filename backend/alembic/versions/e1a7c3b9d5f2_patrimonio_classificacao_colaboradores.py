# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela dos colaboradores com quem uma lista de inservíveis ou extraviados é compartilhada.
"""patrimônio: colaboradores da lista de classificação

Revision ID: e1a7c3b9d5f2
Revises: d0f6b2c8e4a9
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "e1a7c3b9d5f2"
down_revision = "d0f6b2c8e4a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patrimonio_classificacao_colaboradores",
        sa.Column("classificacao_id", sa.Uuid(), sa.ForeignKey("patrimonio_classificacoes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("adicionado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_patrimonio_classificacao_colaboradores_usuario_id", "patrimonio_classificacao_colaboradores", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_patrimonio_classificacao_colaboradores_usuario_id", table_name="patrimonio_classificacao_colaboradores")
    op.drop_table("patrimonio_classificacao_colaboradores")
