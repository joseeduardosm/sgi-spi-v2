# Criado por José Eduardo Santana Martins
# Este arquivo serve para acrescentar ao bem os dados que o SAM (Visão Geral) traz e o Patrimônio ainda não guardava.

"""patrimônio: dados do SAM no bem (item, UO, contas contábeis, depreciação, vida útil, incorporação, documento, histórico, estado e responsável)

Revision ID: b3e8d1f6a9c4
Revises: a2d7b9e1c5f3
Create Date: 2026-10-20
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b3e8d1f6a9c4"
down_revision: str | Sequence[str] | None = "a2d7b9e1c5f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUNAS = [
    ("item_codigo", sa.String(20)), ("uo", sa.String(20)), ("tipo_sam", sa.String(40)), ("conta_contabil", sa.String(20)), ("conta_depreciacao", sa.String(20)),
    ("depreciacao_acumulada", sa.Numeric(14, 2)), ("depreciacao_mensal", sa.Numeric(14, 2)), ("vida_util_meses", sa.Integer()), ("meses_depreciados", sa.Integer()),
    ("ultima_depreciacao_ref", sa.String(6)), ("data_incorporacao", sa.Date()), ("empenho", sa.String(40)), ("numero_documento", sa.String(40)),
    ("ultimo_historico", sa.String(120)), ("data_ultimo_historico", sa.Date()), ("estado_sam", sa.String(30)), ("destino_uge", sa.String(20)), ("responsavel_sam", sa.String(120)),
]


def upgrade() -> None:
    """Colunas opcionais: os bens já cadastrados ficam com elas vazias."""
    for nome, tipo in COLUNAS:
        op.add_column("patrimonio_bens", sa.Column(nome, tipo, nullable=True))
    op.create_index("ix_patrimonio_bens_item_codigo", "patrimonio_bens", ["item_codigo"])


def downgrade() -> None:
    op.drop_index("ix_patrimonio_bens_item_codigo", table_name="patrimonio_bens")
    for nome, _ in reversed(COLUNAS):
        op.drop_column("patrimonio_bens", nome)
