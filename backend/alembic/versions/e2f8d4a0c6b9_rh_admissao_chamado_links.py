# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar na admissão os links dos itens criados pelo formulário de nomeação do GLPI.

"""rh: links dos chamados criados pelo formulário de nomeação

Revision ID: e2f8d4a0c6b9
Revises: d1a7c3e9b5f8
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e2f8d4a0c6b9"
down_revision: str | Sequence[str] | None = "d1a7c3e9b5f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rh_admissoes", sa.Column("chamado_links", sa.JSON()))


def downgrade() -> None:
    with op.batch_alter_table("rh_admissoes") as lote:
        lote.drop_column("chamado_links")
