# Criado por José Eduardo Santana Martins
# Este arquivo serve para permitir mais de um dispositivo na mesma porta de rede, em cascata (switch → telefone IP → PC).

"""rede: dispositivos atrás do primeiro na mesma porta (telefone IP → PC)

Revision ID: b6d8f0a2c4e5
Revises: a4c6e8b0d2f3
Create Date: 2026-11-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b6d8f0a2c4e5"
down_revision: str | Sequence[str] | None = "a4c6e8b0d2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria a lista ordenada de dispositivos atrás do primeiro (bem do Patrimônio ou descrição)."""
    op.create_table(
        "rede_dispositivos_atras",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("conexao_id", sa.Uuid, sa.ForeignKey("rede_conexoes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ordem", sa.Integer, nullable=False, server_default="1"),
        sa.Column("bem_id", sa.Uuid, sa.ForeignKey("patrimonio_bens.id", ondelete="SET NULL"), index=True),
        sa.Column("descricao", sa.String(250), nullable=False, server_default=""),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("bem_id IS NOT NULL OR descricao <> ''", name="ck_rede_dispositivos_atras_alvo"),
    )


def downgrade() -> None:
    op.drop_table("rede_dispositivos_atras")
