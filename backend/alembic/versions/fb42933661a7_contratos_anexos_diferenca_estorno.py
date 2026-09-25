# Criado por José Eduardo Santana Martins
# Este arquivo serve para vincular anexos aos contratos e registrar competências de diferença de reajuste e estornos de NE.
"""contratos: vínculo dos anexos, competência de diferença de reajuste e estorno na NE

- `anexos.contrato_id`: contrato dono do arquivo (a exclusão do contrato descarta todos os arquivos dele).
- `contratos_competencias.tipo` e `reajuste_id`: competência complementar que paga a diferença de um
  reajuste retroativo; a unicidade passa a ser (contrato, início do período, tipo).
- `contratos_notas_empenho_movimentos`: lançamentos de estorno (débito negativo), com autor e
  justificativa; deixa de haver um único lançamento por (NE, competência).

Revision ID: fb42933661a7
Revises: 84d049d7fa1a
Create Date: 2026-09-24 10:35:38
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fb42933661a7"
down_revision: str | Sequence[str] | None = "84d049d7fa1a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("anexos", sa.Column("contrato_id", sa.Uuid(), nullable=True))
    op.create_index("ix_anexos_contrato_id", "anexos", ["contrato_id"])

    op.add_column("contratos_competencias", sa.Column("tipo", sa.String(length=30), server_default="regular", nullable=False))
    op.add_column("contratos_competencias", sa.Column("reajuste_id", sa.Uuid(), nullable=True))
    op.drop_constraint("contratos_competencias_contrato_id_periodo_inicio_key", "contratos_competencias", type_="unique")
    op.create_unique_constraint(
        "contratos_competencias_contrato_id_periodo_inicio_tipo_key", "contratos_competencias", ["contrato_id", "periodo_inicio", "tipo"]
    )
    op.create_check_constraint("ck_contratos_competencias_tipo", "contratos_competencias", "tipo IN ('regular', 'diferenca_reajuste')")
    op.create_index("ix_contratos_competencias_reajuste_id", "contratos_competencias", ["reajuste_id"])
    op.create_foreign_key(
        "contratos_competencias_reajuste_id_fkey", "contratos_competencias", "contratos_reajustes", ["reajuste_id"], ["id"], ondelete="SET NULL"
    )

    op.add_column("contratos_notas_empenho_movimentos", sa.Column("justificativa", sa.String(length=2000), server_default="", nullable=False))
    op.add_column("contratos_notas_empenho_movimentos", sa.Column("criado_por_id", sa.Integer(), nullable=True))
    op.drop_constraint("contratos_notas_empenho_movimentos_nota_id_competencia_id_key", "contratos_notas_empenho_movimentos", type_="unique")
    op.create_check_constraint("ck_contratos_ne_movimentos_tipo", "contratos_notas_empenho_movimentos", "tipo IN ('pagamento', 'estorno')")
    op.create_foreign_key(
        "contratos_notas_empenho_movimentos_criado_por_id_fkey", "contratos_notas_empenho_movimentos", "usuarios",
        ["criado_por_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("contratos_notas_empenho_movimentos_criado_por_id_fkey", "contratos_notas_empenho_movimentos", type_="foreignkey")
    op.drop_constraint("ck_contratos_ne_movimentos_tipo", "contratos_notas_empenho_movimentos", type_="check")
    op.execute("DELETE FROM contratos_notas_empenho_movimentos WHERE tipo = 'estorno'")
    op.create_unique_constraint(
        "contratos_notas_empenho_movimentos_nota_id_competencia_id_key", "contratos_notas_empenho_movimentos", ["nota_id", "competencia_id"]
    )
    op.drop_column("contratos_notas_empenho_movimentos", "criado_por_id")
    op.drop_column("contratos_notas_empenho_movimentos", "justificativa")

    op.drop_constraint("contratos_competencias_reajuste_id_fkey", "contratos_competencias", type_="foreignkey")
    op.drop_index("ix_contratos_competencias_reajuste_id", table_name="contratos_competencias")
    op.drop_constraint("ck_contratos_competencias_tipo", "contratos_competencias", type_="check")
    op.execute("DELETE FROM contratos_competencias WHERE tipo = 'diferenca_reajuste'")
    op.drop_constraint("contratos_competencias_contrato_id_periodo_inicio_tipo_key", "contratos_competencias", type_="unique")
    op.create_unique_constraint("contratos_competencias_contrato_id_periodo_inicio_key", "contratos_competencias", ["contrato_id", "periodo_inicio"])
    op.drop_column("contratos_competencias", "reajuste_id")
    op.drop_column("contratos_competencias", "tipo")

    op.drop_index("ix_anexos_contrato_id", table_name="anexos")
    op.drop_column("anexos", "contrato_id")
