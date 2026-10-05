# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as colunas do reaproveitamento de documentos do checklist entre contratos da mesma empresa.
"""checklist: documento da empresa (reaproveitamento entre contratos)

- `contratos_checklists_itens.vale_outros_contratos`: o item é um documento da empresa (ex.: certidão);
- `contratos_competencias_documentos.vale_outros_contratos`: cópia dessa marca na competência;
- `contratos_competencias_documentos.reaproveitado_contrato`: número do contrato de onde o arquivo foi reaproveitado.

Revision ID: b8d2f6a4c1e7
Revises: a7c1e5b9d3f4
Create Date: 2026-10-05 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b8d2f6a4c1e7"
down_revision: str | Sequence[str] | None = "a7c1e5b9d3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Itens e documentos existentes começam sem a marca (nada muda até alguém marcar)."""
    op.add_column("contratos_checklists_itens", sa.Column("vale_outros_contratos", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("contratos_competencias_documentos", sa.Column("vale_outros_contratos", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("contratos_competencias_documentos", sa.Column("reaproveitado_contrato", sa.String(length=60), nullable=True))


def downgrade() -> None:
    """Remove as colunas."""
    op.drop_column("contratos_competencias_documentos", "reaproveitado_contrato")
    op.drop_column("contratos_competencias_documentos", "vale_outros_contratos")
    op.drop_column("contratos_checklists_itens", "vale_outros_contratos")
