# Criado por José Eduardo Santana Martins
# Este arquivo serve para tornar o CPF do preposto opcional (coluna aceita nulo).
"""contratos: CPF do preposto deixa de ser obrigatório

Revision ID: f9c3e7a1b5d2
Revises: e8b2d6f0a4c3
Create Date: 2026-10-06 21:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f9c3e7a1b5d2"
down_revision: str | Sequence[str] | None = "e8b2d6f0a4c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """A coluna passa a aceitar nulo; a unicidade (empresa, CPF) continua valendo para os CPFs informados."""
    op.alter_column("contratos_empresas_prepostos", "cpf", existing_type=sa.String(length=11), nullable=True)


def downgrade() -> None:
    """Volta a exigir o CPF (prepostos sem CPF recebem 00000000000 acrescido de um sufixo único para não colidir)."""
    op.execute(
        "UPDATE contratos_empresas_prepostos p SET cpf = lpad(n.numero::text, 11, '0') FROM "
        "(SELECT id, row_number() OVER (ORDER BY criado_em, id) AS numero FROM contratos_empresas_prepostos WHERE cpf IS NULL) n "
        "WHERE p.id = n.id"
    )
    op.alter_column("contratos_empresas_prepostos", "cpf", existing_type=sa.String(length=11), nullable=False)
