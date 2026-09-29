# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar o cadastro de feriados e pontos facultativos do Módulo RH.
"""rh: feriados e pontos facultativos

- `rh_feriados`: um registro por data (feriado ou ponto facultativo; nacional, estadual ou municipal).
- `rh_parametros.inicio_vedado_feriado`: períodos não podem começar nessas datas (desligado por padrão).

Revision ID: 9c5e7a1b3d4f
Revises: 8b4d6f0a2c3e
Create Date: 2026-09-29 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "9c5e7a1b3d4f"
down_revision: str | Sequence[str] | None = "8b4d6f0a2c3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria a tabela de feriados e o parâmetro."""
    op.create_table(
        "rh_feriados",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("descricao", sa.String(length=200), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("abrangencia", sa.String(length=10), nullable=False),
        sa.Column("atualizado_por_nome", sa.String(length=200), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tipo IN ('feriado', 'ponto_facultativo')", name="ck_rh_feriados_tipo"),
        sa.CheckConstraint("abrangencia IN ('nacional', 'estadual', 'municipal')", name="ck_rh_feriados_abrangencia"),
        sa.PrimaryKeyConstraint("id", name="rh_feriados_pkey"),
        sa.UniqueConstraint("data", name="rh_feriados_data_key"),
    )
    op.add_column("rh_parametros", sa.Column("inicio_vedado_feriado", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    """Remove o parâmetro e a tabela."""
    op.drop_column("rh_parametros", "inicio_vedado_feriado")
    op.drop_table("rh_feriados")
