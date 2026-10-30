# Criado por José Eduardo Santana Martins
# Este arquivo serve para trocar os meses integrais do reajuste por uma escolha só (pro rata ou integral) para todos os meses quebrados.
"""reajuste: calculo_mes_quebrado no lugar de meses_integrais

A escolha de como calcular os meses quebrados pela data de efeito passa a ser uma só para o reajuste
inteiro ("pro_rata" ou "integral"), em vez de uma lista de meses. Reajuste que tinha algum mês marcado
como integral vira "integral"; os demais ficam sem escolha (o gestor escolhe na tela).

Revision ID: f2b8d4a6c1e3
Revises: e4c7a9b2d6f1
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# ────────────────────────────────────────────────────────────────────────────
revision = "f2b8d4a6c1e3"
down_revision = "e4c7a9b2d6f1"
branch_labels = None
depends_on = None
# ────────────────────────────────────────────────────────────────────────────


def upgrade() -> None:
    op.add_column(
        "contratos_reajustes",
        sa.Column(
            "calculo_mes_quebrado",
            sa.String(10),
            nullable=True,
            comment='Cálculo dos meses quebrados pela data de efeito: "pro_rata" ou "integral"; nulo = ainda não escolhido.',
        ),
    )
    op.execute("UPDATE contratos_reajustes SET calculo_mes_quebrado = 'integral' WHERE jsonb_array_length(meses_integrais) > 0")
    op.drop_column("contratos_reajustes", "meses_integrais")


def downgrade() -> None:
    op.add_column(
        "contratos_reajustes",
        sa.Column("meses_integrais", JSONB(), nullable=False, server_default="[]"),
    )
    op.drop_column("contratos_reajustes", "calculo_mes_quebrado")
