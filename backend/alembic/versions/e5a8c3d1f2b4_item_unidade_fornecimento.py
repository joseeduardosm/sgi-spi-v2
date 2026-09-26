# Criado por José Eduardo Santana Martins
# Este arquivo serve para acrescentar a Unidade de Fornecimento (UF) aos itens do contrato.
"""contratos: unidade de fornecimento (UF) dos itens

Coluna de texto `unidade_fornecimento` em `contratos_itens` (ex.: "posto", "hora", "unidade").
Itens existentes ficam com o campo vazio, a preencher editando o contrato.

Revision ID: e5a8c3d1f2b4
Revises: d4f7b2c9e1a3
Create Date: 2026-09-26 02:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e5a8c3d1f2b4"
down_revision: str | Sequence[str] | None = "d4f7b2c9e1a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Acrescenta a coluna; o valor padrão vazio preenche os itens já cadastrados."""
    op.add_column("contratos_itens", sa.Column("unidade_fornecimento", sa.String(length=50), server_default="", nullable=False))


def downgrade() -> None:
    """Remove a coluna."""
    op.drop_column("contratos_itens", "unidade_fornecimento")
