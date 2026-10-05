# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela das telas favoritas de cada usuário (atalhos do menu lateral).
"""usuarios_favoritos: telas fixadas pelo usuário no menu

Revision ID: c9e3a7f1b5d8
Revises: b8d2f6a4c1e7
Create Date: 2026-10-05 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "c9e3a7f1b5d8"
down_revision: str | Sequence[str] | None = "b8d2f6a4c1e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria a tabela (uma linha por usuário e rota); apagar o usuário apaga os favoritos."""
    op.create_table(
        "usuarios_favoritos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rota", sa.String(length=300), nullable=False),
        sa.Column("rotulo", sa.String(length=120), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("usuario_id", "rota", name="uq_usuarios_favoritos_rota"),
    )
    op.create_index("ix_usuarios_favoritos_usuario_id", "usuarios_favoritos", ["usuario_id"])


def downgrade() -> None:
    """Remove a tabela."""
    op.drop_index("ix_usuarios_favoritos_usuario_id", table_name="usuarios_favoritos")
    op.drop_table("usuarios_favoritos")
