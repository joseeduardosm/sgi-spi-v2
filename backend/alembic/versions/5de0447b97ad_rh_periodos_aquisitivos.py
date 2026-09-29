# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar os períodos aquisitivos de férias (crédito automático e expiração) no Módulo RH.
"""rh: períodos aquisitivos de férias

- `rh_dados_funcionais.inicio_aquisitivo_dia`/`_mes`: início do período aquisitivo (só dia e mês; repete todo ano).
- `rh_periodos_aquisitivos`: um registro por período de 12 meses, com os dias creditados e a expiração.
- `rh_afastamentos.periodo_aquisitivo_id`: período cujo saldo as férias debitam.
- `rh_parametros`: dias creditados por período (30), folga do aviso de expiração (15) e aviso ativo.

Revision ID: 5de0447b97ad
Revises: 6be74b4141cb
Create Date: 2026-09-29 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "5de0447b97ad"
down_revision: str | Sequence[str] | None = "6be74b4141cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CK_INICIO = (
    "(inicio_aquisitivo_dia IS NULL AND inicio_aquisitivo_mes IS NULL) OR "
    "(inicio_aquisitivo_mes BETWEEN 1 AND 12 AND inicio_aquisitivo_dia BETWEEN 1 AND "
    "CASE WHEN inicio_aquisitivo_mes = 2 THEN 29 WHEN inicio_aquisitivo_mes IN (4, 6, 9, 11) THEN 30 ELSE 31 END)"
)


def upgrade() -> None:
    """Cria a tabela de períodos, as colunas novas e os parâmetros (com os valores iniciais)."""
    op.create_table(
        "rh_periodos_aquisitivos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("inicio", sa.Date(), nullable=False),
        sa.Column("fim", sa.Date(), nullable=False),
        sa.Column("dias_creditados", sa.Integer(), nullable=False),
        sa.Column("origem", sa.String(length=12), nullable=False),
        sa.Column("ajustado_por_nome", sa.String(length=200), nullable=True),
        sa.Column("expirado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dias_expirados", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("origem IN ('automatico', 'ajuste_cgp')", name="ck_rh_periodos_aquisitivos_origem"),
        sa.CheckConstraint("fim > inicio", name="ck_rh_periodos_aquisitivos_datas"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE", name="rh_periodos_aquisitivos_usuario_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="rh_periodos_aquisitivos_pkey"),
        sa.UniqueConstraint("usuario_id", "inicio", name="uq_rh_periodos_aquisitivos_usuario_inicio"),
    )
    op.create_index("ix_rh_periodos_aquisitivos_usuario_id", "rh_periodos_aquisitivos", ["usuario_id"])
    op.add_column("rh_afastamentos", sa.Column("periodo_aquisitivo_id", sa.Uuid(), nullable=True))
    op.create_index("ix_rh_afastamentos_periodo_aquisitivo_id", "rh_afastamentos", ["periodo_aquisitivo_id"])
    op.create_foreign_key("rh_afastamentos_periodo_aquisitivo_id_fkey", "rh_afastamentos", "rh_periodos_aquisitivos",
                          ["periodo_aquisitivo_id"], ["id"], ondelete="SET NULL")
    op.add_column("rh_dados_funcionais", sa.Column("inicio_aquisitivo_dia", sa.Integer(), nullable=True))
    op.add_column("rh_dados_funcionais", sa.Column("inicio_aquisitivo_mes", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_rh_dados_funcionais_inicio_aquisitivo", "rh_dados_funcionais", CK_INICIO)
    op.add_column("rh_parametros", sa.Column("dias_ferias_por_periodo", sa.Integer(), server_default="30", nullable=False))
    op.add_column("rh_parametros", sa.Column("folga_aviso_ferias_dias", sa.Integer(), server_default="15", nullable=False))
    op.add_column("rh_parametros", sa.Column("aviso_ferias_ativo", sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    """Remove as colunas, a tabela de períodos e os parâmetros novos."""
    op.drop_column("rh_parametros", "aviso_ferias_ativo")
    op.drop_column("rh_parametros", "folga_aviso_ferias_dias")
    op.drop_column("rh_parametros", "dias_ferias_por_periodo")
    op.drop_constraint("ck_rh_dados_funcionais_inicio_aquisitivo", "rh_dados_funcionais", type_="check")
    op.drop_column("rh_dados_funcionais", "inicio_aquisitivo_mes")
    op.drop_column("rh_dados_funcionais", "inicio_aquisitivo_dia")
    op.drop_constraint("rh_afastamentos_periodo_aquisitivo_id_fkey", "rh_afastamentos", type_="foreignkey")
    op.drop_index("ix_rh_afastamentos_periodo_aquisitivo_id", table_name="rh_afastamentos")
    op.drop_column("rh_afastamentos", "periodo_aquisitivo_id")
    op.drop_index("ix_rh_periodos_aquisitivos_usuario_id", table_name="rh_periodos_aquisitivos")
    op.drop_table("rh_periodos_aquisitivos")
