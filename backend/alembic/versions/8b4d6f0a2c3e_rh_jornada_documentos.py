# Criado por José Eduardo Santana Martins
# Este arquivo serve para acrescentar aos dados funcionais do RH a jornada, os horários e os documentos (exclusivos da CGP).
"""rh: jornada, horários e documentos nos dados funcionais

`rh_dados_funcionais` ganha: `jornada_semanal_horas` (1–80), `regime_plantao`, `horario_trabalho_inicio`/`_fim`,
`horario_estudante`, `intervalo_inicio`/`_fim` (início e fim juntos ou nenhum), `rg_cin` e `rs_pv`.

Revision ID: 8b4d6f0a2c3e
Revises: 7a3c5e9f1b2d
Create Date: 2026-09-29 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "8b4d6f0a2c3e"
down_revision: str | Sequence[str] | None = "7a3c5e9f1b2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELA = "rh_dados_funcionais"


def upgrade() -> None:
    """Cria as colunas e as regras de consistência."""
    op.add_column(TABELA, sa.Column("jornada_semanal_horas", sa.Integer(), nullable=True))
    op.add_column(TABELA, sa.Column("regime_plantao", sa.Boolean(), server_default="false", nullable=False))
    op.add_column(TABELA, sa.Column("horario_trabalho_inicio", sa.Time(), nullable=True))
    op.add_column(TABELA, sa.Column("horario_trabalho_fim", sa.Time(), nullable=True))
    op.add_column(TABELA, sa.Column("horario_estudante", sa.Boolean(), server_default="false", nullable=False))
    op.add_column(TABELA, sa.Column("intervalo_inicio", sa.Time(), nullable=True))
    op.add_column(TABELA, sa.Column("intervalo_fim", sa.Time(), nullable=True))
    op.add_column(TABELA, sa.Column("rg_cin", sa.String(length=30), nullable=True))
    op.add_column(TABELA, sa.Column("rs_pv", sa.String(length=30), nullable=True))
    op.create_check_constraint("ck_rh_dados_funcionais_jornada", TABELA, "jornada_semanal_horas IS NULL OR jornada_semanal_horas BETWEEN 1 AND 80")
    op.create_check_constraint("ck_rh_dados_funcionais_horario", TABELA, "(horario_trabalho_inicio IS NULL) = (horario_trabalho_fim IS NULL)")
    op.create_check_constraint("ck_rh_dados_funcionais_intervalo", TABELA, "(intervalo_inicio IS NULL) = (intervalo_fim IS NULL)")


def downgrade() -> None:
    """Remove as regras e as colunas."""
    for nome in ("ck_rh_dados_funcionais_intervalo", "ck_rh_dados_funcionais_horario", "ck_rh_dados_funcionais_jornada"):
        op.drop_constraint(nome, TABELA, type_="check")
    for coluna in ("rs_pv", "rg_cin", "intervalo_fim", "intervalo_inicio", "horario_estudante", "horario_trabalho_fim",
                   "horario_trabalho_inicio", "regime_plantao", "jornada_semanal_horas"):
        op.drop_column(TABELA, coluna)
