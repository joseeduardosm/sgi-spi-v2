# Criado por José Eduardo Santana Martins
# Este arquivo serve para restringir um assunto dos Chamados a setores ("Quem pode escolher este assunto": ex.: CGP > Nomeação só para a CGP).

"""chamados: setores que podem escolher o assunto

Revision ID: c8e0a2b4d6f7
Revises: b6d8f0a2c4e5
Create Date: 2026-11-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "c8e0a2b4d6f7"
down_revision: str | Sequence[str] | None = "b6d8f0a2c4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Assunto × setor: com linhas, só os membros desses setores (e dos de baixo) escolhem o assunto."""
    op.create_table(
        "chamados_categorias_setores",
        sa.Column("categoria_id", sa.Uuid, sa.ForeignKey("chamados_categorias.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("setor_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="CASCADE"), primary_key=True, index=True),
    )


def downgrade() -> None:
    op.drop_table("chamados_categorias_setores")
