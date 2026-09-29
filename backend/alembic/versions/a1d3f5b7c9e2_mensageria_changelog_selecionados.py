# Criado por José Eduardo Santana Martins
# Este arquivo serve para permitir o envio do e-mail de changelog a usuários e setores escolhidos.
"""mensageria: e-mail de changelog para usuários e setores escolhidos

- `mensageria_envios_changelog.destino` aceita `selecionados` (além de `todos` e `teste`) e passa a ter 12 caracteres.
- `destino_descricao`: quem foi escolhido (nomes dos usuários e dos setores), para o histórico.

Revision ID: a1d3f5b7c9e2
Revises: 9c5e7a1b3d4f
Create Date: 2026-09-29 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a1d3f5b7c9e2"
down_revision: str | Sequence[str] | None = "9c5e7a1b3d4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELA = "mensageria_envios_changelog"
CHECK = "ck_mensageria_envios_changelog_destino"


def upgrade() -> None:
    """Amplia o destino e cria a descrição da seleção."""
    op.drop_constraint(CHECK, TABELA, type_="check")
    op.alter_column(TABELA, "destino", type_=sa.String(length=12), existing_type=sa.String(length=10), existing_nullable=False)
    op.create_check_constraint(CHECK, TABELA, "destino IN ('todos', 'teste', 'selecionados')")
    op.add_column(TABELA, sa.Column("destino_descricao", sa.Text(), nullable=True))


def downgrade() -> None:
    """Volta ao destino `todos`/`teste` (envios `selecionados` viram `teste` para caber na regra antiga)."""
    op.drop_column(TABELA, "destino_descricao")
    op.drop_constraint(CHECK, TABELA, type_="check")
    op.execute(f"UPDATE {TABELA} SET destino = 'teste' WHERE destino = 'selecionados'")
    op.alter_column(TABELA, "destino", type_=sa.String(length=10), existing_type=sa.String(length=12), existing_nullable=False)
    op.create_check_constraint(CHECK, TABELA, "destino IN ('todos', 'teste')")
