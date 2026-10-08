# Criado por José Eduardo Santana Martins
# Este arquivo serve para acrescentar a opção "Pedir para enviar" aos documentos do checklist.
"""contratos: documento do checklist ganha `pedir_envio` (pedido de envio no e-mail da medição concluída)

Revision ID: a1d4f8c2e6b9
Revises: f9c3e7a1b5d2
Create Date: 2026-10-06 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a1d4f8c2e6b9"
down_revision: str | Sequence[str] | None = "f9c3e7a1b5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Acrescenta a coluna (padrão `false`: nenhum documento é pedido até a equipe marcar)."""
    op.add_column("contratos_checklists_itens", sa.Column("pedir_envio", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("contratos_checklists_itens", "pedir_envio")
