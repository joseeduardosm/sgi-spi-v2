# Criado por José Eduardo Santana Martins
# Este arquivo serve para permitir o número do contrato em formato livre.
"""contratos: número em formato livre

- Nova coluna `contratos.numero` (texto, até 60 caracteres), preenchida nos contratos existentes com o
  número no formato antigo (`012/2026`), e índice único por `lower(numero)`.
- `sequencial` e `ano` passam a ser opcionais (só preenchidos quando o número segue NNN/AAAA) e deixam de
  ser únicos em conjunto.

Revision ID: 46921c091299
Revises: 0ecc10bd1805
Create Date: 2026-09-28 21:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "46921c091299"
down_revision: str | Sequence[str] | None = "0ecc10bd1805"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria e preenche o número livre; afrouxa sequencial/ano."""
    op.add_column("contratos", sa.Column("numero", sa.String(length=60), nullable=True))
    op.execute("UPDATE contratos SET numero = lpad(sequencial::text, 3, '0') || '/' || lpad(ano::text, 4, '0')")
    op.alter_column("contratos", "numero", existing_type=sa.String(length=60), nullable=False)
    op.create_index("ux_contratos_numero", "contratos", [sa.text("lower(numero)")], unique=True)
    op.drop_constraint("contratos_sequencial_ano_key", "contratos", type_="unique")
    op.alter_column("contratos", "sequencial", existing_type=sa.Integer(), nullable=True)
    op.alter_column("contratos", "ano", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Volta ao número NNN/AAAA. Falha se houver contrato com número fora desse padrão (sequencial/ano nulos)."""
    op.alter_column("contratos", "ano", existing_type=sa.Integer(), nullable=False)
    op.alter_column("contratos", "sequencial", existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint("contratos_sequencial_ano_key", "contratos", ["sequencial", "ano"])
    op.drop_index("ux_contratos_numero", table_name="contratos")
    op.drop_column("contratos", "numero")
