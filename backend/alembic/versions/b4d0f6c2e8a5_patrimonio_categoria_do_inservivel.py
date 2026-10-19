# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar a categoria do bem inservível (ocioso, recuperável, antieconômico, irrecuperável) na lista e no bem.
"""patrimônio: categoria do inservível

`patrimonio_itens_classificacao.categoria` (escolhida junto com a justificativa) e `patrimonio_bens.categoria_inservivel` (definida quando a lista é
aprovada). Os inservíveis já aprovados ficam sem categoria (só "Inservível").

Revision ID: b4d0f6c2e8a5
Revises: a3c9e5b1d7f4
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "b4d0f6c2e8a5"
down_revision = "a3c9e5b1d7f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patrimonio_itens_classificacao", sa.Column("categoria", sa.String(15), nullable=True))
    op.add_column("patrimonio_bens", sa.Column("categoria_inservivel", sa.String(15), nullable=True))


def downgrade() -> None:
    op.drop_column("patrimonio_bens", "categoria_inservivel")
    op.drop_column("patrimonio_itens_classificacao", "categoria")
