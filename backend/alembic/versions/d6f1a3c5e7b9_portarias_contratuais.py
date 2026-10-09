# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas das autoridades signatárias e das portarias de designação dos contratos.
"""portarias contratuais: autoridades signatárias e portarias dos contratos

Revision ID: d6f1a3c5e7b9
Revises: c5e8a2b6d9f1
Create Date: 2026-10-09 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d6f1a3c5e7b9"
down_revision: str | Sequence[str] | None = "c5e8a2b6d9f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria as duas tabelas (nada existente é alterado)."""
    op.create_table(
        "portarias_autoridades",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sigla", sa.String(length=60), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("cargo", sa.String(length=200), nullable=False),
        sa.Column("setor", sa.String(length=200), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "contratos_portarias",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("contrato_id", sa.Uuid(), sa.ForeignKey("contratos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("autoridade_id", sa.Uuid(), sa.ForeignKey("portarias_autoridades.id", ondelete="SET NULL"), nullable=True),
        sa.Column("numero_protocolo_id", sa.Uuid(), sa.ForeignKey("protocolo_numeros.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sigla", sa.String(length=60), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("exercicio", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="aguardando_aceite"),
        sa.Column("portaria_anterior_id", sa.Uuid(), sa.ForeignKey("contratos_portarias.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dados", sa.dialects.postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("motivo", sa.Text(), nullable=False, server_default=""),
        sa.Column("solicitada_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("solicitada_por_nome", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("solicitada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("aceita_por_nome", sa.String(length=200), nullable=True),
        sa.Column("aceita_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publicada_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_contratos_portarias_contrato_id", "contratos_portarias", ["contrato_id"])
    op.create_index("ix_contratos_portarias_numero_protocolo_id", "contratos_portarias", ["numero_protocolo_id"])
    op.create_index("ix_contratos_portarias_status", "contratos_portarias", ["status"])


def downgrade() -> None:
    """Remove as tabelas."""
    op.drop_table("contratos_portarias")
    op.drop_table("portarias_autoridades")
