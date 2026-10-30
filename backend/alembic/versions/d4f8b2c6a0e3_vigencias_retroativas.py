# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela das vigências retroativas e a marca de reajuste retroativo.

"""contratos: vigências retroativas e reajuste retroativo

Revision ID: d4f8b2c6a0e3
Revises: a7c1e5b9d3f6
Create Date: 2026-10-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d4f8b2c6a0e3"
down_revision: str | Sequence[str] | None = "a7c1e5b9d3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contratos_vigencias_retroativas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("contrato_id", sa.Uuid(), sa.ForeignKey("contratos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meses", sa.Integer(), nullable=False),
        sa.Column("assinada_em", sa.Date(), nullable=False),
        sa.Column("numero_termo", sa.String(100), nullable=False, server_default=""),
        sa.Column("data_inicio", sa.Date(), nullable=False),
        sa.Column("data_fim", sa.Date(), nullable=False),
        sa.Column("inicio_anterior", sa.Date(), nullable=False),
        sa.Column("anexo_id", sa.Uuid(), sa.ForeignKey("anexos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("codigo_documento", sa.Integer()),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("contrato_id", "data_inicio"),
    )
    op.create_index("ix_contratos_vigencias_retroativas_contrato_id", "contratos_vigencias_retroativas", ["contrato_id"])
    op.add_column("contratos_reajustes", sa.Column("retroativo", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("contratos_reajustes", "retroativo")
    op.drop_index("ix_contratos_vigencias_retroativas_contrato_id", table_name="contratos_vigencias_retroativas")
    op.drop_table("contratos_vigencias_retroativas")
