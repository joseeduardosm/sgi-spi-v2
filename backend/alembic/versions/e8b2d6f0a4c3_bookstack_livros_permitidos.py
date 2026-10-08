# Criado por José Eduardo Santana Martins
# Este arquivo serve para acrescentar à integração com o BookStack a lista de livros exibidos no portal.
"""bookstack: coluna `livros_permitidos` (ids dos livros que o portal mostra; vazio = todos)

Revision ID: e8b2d6f0a4c3
Revises: d7a1c5e9b3f2
Create Date: 2026-10-06 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e8b2d6f0a4c3"
down_revision: str | Sequence[str] | None = "d7a1c5e9b3f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Acrescenta a coluna (vazia = todos os livros que a conta de serviço enxerga)."""
    op.add_column("integracao_bookstack", sa.Column("livros_permitidos", sa.String(length=200), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("integracao_bookstack", "livros_permitidos")
