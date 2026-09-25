# Criado por José Eduardo Santana Martins
# Este arquivo serve para marcar cada documento do checklist como obrigatório ou opcional.
"""checklist: documentos obrigatórios ou opcionais

Cada documento do checklist (e a cópia dele na competência) passa a indicar se é obrigatório.
Os documentos já existentes ficam obrigatórios, preservando o comportamento anterior.

Revision ID: 9f9b0de79c5a
Revises: fb42933661a7
Create Date: 2026-09-25 09:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior (o Alembic encadeia as migrações por esses ids)
revision: str = "9f9b0de79c5a"
down_revision: str | Sequence[str] | None = "fb42933661a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tabelas que recebem a coluna: o item do checklist e a cópia dele em cada competência
TABELAS = ("contratos_checklists_itens", "contratos_competencias_documentos")


def upgrade() -> None:
    """Acrescenta a coluna `obrigatorio`; linhas existentes recebem verdadeiro (server_default)."""
    for tabela in TABELAS:
        op.add_column(tabela, sa.Column("obrigatorio", sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    """Desfaz: remove a coluna das duas tabelas."""
    for tabela in TABELAS:
        op.drop_column(tabela, "obrigatorio")
