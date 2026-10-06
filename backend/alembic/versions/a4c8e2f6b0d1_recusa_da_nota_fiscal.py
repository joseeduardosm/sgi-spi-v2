# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela das recusas de nota fiscal pelo Financeiro (ciclo nota → recusa → nova nota → aprovação).
"""contratos: recusas da nota fiscal na retenção de tributos

Revision ID: a4c8e2f6b0d1
Revises: f3b7d1e9a5c4
Create Date: 2026-10-06 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# Identificação da migração: esta revisão e a anterior
revision: str = "a4c8e2f6b0d1"
down_revision: str | Sequence[str] | None = "f3b7d1e9a5c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria a tabela de recusas (uma linha por recusa, em ordem, com o retrato das notas recusadas e o PDF da recusa)."""
    op.create_table(
        "contratos_competencias_recusas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("competencia_id", sa.Uuid(), sa.ForeignKey("contratos_competencias.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.Column("recusada_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recusada_por_nome", sa.String(length=250), nullable=False, server_default=""),
        sa.Column("recusada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notas", sa.JSON(), nullable=False),
        sa.Column("pdf_anexo_id", sa.Uuid(), sa.ForeignKey("anexos.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("email_enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_ok", sa.Boolean(), nullable=True),
        sa.Column("email_destinatarios", sa.JSON(), nullable=False),
        sa.Column("email_erro", sa.Text(), nullable=True),
        sa.UniqueConstraint("competencia_id", "ordem", name="uq_contratos_recusas_competencia_ordem"),
    )
    op.create_index("ix_contratos_competencias_recusas_competencia_id", "contratos_competencias_recusas", ["competencia_id"])


def downgrade() -> None:
    """Remove a tabela."""
    op.drop_index("ix_contratos_competencias_recusas_competencia_id", table_name="contratos_competencias_recusas")
    op.drop_table("contratos_competencias_recusas")
