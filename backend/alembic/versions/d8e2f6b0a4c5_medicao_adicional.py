# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a medição adicional (outra medição e outro pagamento no mesmo mês de uma competência).
"""contratos: medição adicional

Revision ID: d8e2f6b0a4c5
Revises: c7d1e5a9b3f4
Create Date: 2026-10-07 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8e2f6b0a4c5"
down_revision: str | Sequence[str] | None = "c7d1e5a9b3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOME_UNICO = "contratos_competencias_contrato_id_periodo_inicio_tipo_key"


def upgrade() -> None:
    """Checkbox no contrato, colunas da medição adicional, novo tipo e unicidade que admite várias adicionais por período."""
    op.add_column("contratos", sa.Column("permite_medicao_adicional", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("contratos_competencias", sa.Column("numero_adicional", sa.Integer(), server_default="0", nullable=False))
    op.add_column("contratos_competencias", sa.Column("adicional_justificativa", sa.Text(), server_default="", nullable=False))
    op.add_column("contratos_competencias", sa.Column("adicional_anexo_id", sa.Uuid(), nullable=True))
    op.add_column("contratos_competencias", sa.Column("adicional_por_nome", sa.String(length=250), server_default="", nullable=False))
    op.create_foreign_key("fk_contratos_competencias_adicional_anexo", "contratos_competencias", "anexos", ["adicional_anexo_id"], ["id"], ondelete="RESTRICT")
    op.drop_constraint("ck_contratos_competencias_tipo", "contratos_competencias", type_="check")
    op.create_check_constraint("ck_contratos_competencias_tipo", "contratos_competencias", "tipo IN ('regular', 'diferenca_reajuste', 'adicional')")
    op.drop_constraint(NOME_UNICO, "contratos_competencias", type_="unique")
    op.create_unique_constraint(NOME_UNICO, "contratos_competencias", ["contrato_id", "periodo_inicio", "tipo", "numero_adicional"])


def downgrade() -> None:
    """Remove a medição adicional (as competências adicionais existentes são apagadas)."""
    op.execute("DELETE FROM contratos_competencias WHERE tipo = 'adicional'")
    op.drop_constraint(NOME_UNICO, "contratos_competencias", type_="unique")
    op.create_unique_constraint(NOME_UNICO, "contratos_competencias", ["contrato_id", "periodo_inicio", "tipo"])
    op.drop_constraint("ck_contratos_competencias_tipo", "contratos_competencias", type_="check")
    op.create_check_constraint("ck_contratos_competencias_tipo", "contratos_competencias", "tipo IN ('regular', 'diferenca_reajuste')")
    op.drop_constraint("fk_contratos_competencias_adicional_anexo", "contratos_competencias", type_="foreignkey")
    op.drop_column("contratos_competencias", "adicional_por_nome")
    op.drop_column("contratos_competencias", "adicional_anexo_id")
    op.drop_column("contratos_competencias", "adicional_justificativa")
    op.drop_column("contratos_competencias", "numero_adicional")
    op.drop_column("contratos", "permite_medicao_adicional")
