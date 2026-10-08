# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela dos PDFs autenticados pelo sistema (Folha de autenticação com código de verificação).
"""documentos autenticados: código de verificação, hash e retrato de quem deu ciência

Revision ID: c5e8a2b6d9f1
Revises: b4d7f1a9c2e6
Create Date: 2026-10-08 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "c5e8a2b6d9f1"
down_revision: str | Sequence[str] | None = "b4d7f1a9c2e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria a tabela (os documentos já gerados não são alterados)."""
    op.create_table(
        "contratos_documentos_autenticados",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("codigo", sa.String(length=32), nullable=False),
        sa.Column("sha256_conteudo", sa.String(length=64), nullable=False),
        sa.Column("sha256_final", sa.String(length=64), nullable=False),
        sa.Column("tipo", sa.String(length=60), nullable=False),
        sa.Column("contrato_id", sa.Uuid(), sa.ForeignKey("contratos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("competencia_id", sa.Uuid(), sa.ForeignKey("contratos_competencias.id", ondelete="SET NULL"), nullable=True),
        sa.Column("anexo_id", sa.Uuid(), sa.ForeignKey("anexos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("gerado_por_nome", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("gerado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ciencias", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_contratos_documentos_autenticados_codigo", "contratos_documentos_autenticados", ["codigo"])
    op.create_index("ix_contratos_documentos_autenticados_sha256_final", "contratos_documentos_autenticados", ["sha256_final"])
    op.create_index("ix_contratos_documentos_autenticados_contrato_id", "contratos_documentos_autenticados", ["contrato_id"])


def downgrade() -> None:
    """Remove a tabela."""
    op.drop_table("contratos_documentos_autenticados")
