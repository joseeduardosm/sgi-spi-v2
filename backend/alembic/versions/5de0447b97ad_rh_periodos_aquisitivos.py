"""
===============================================================================
ARQUIVO: 5de0447b97ad_rh_periodos_aquisitivos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Criar no Módulo RH os períodos aquisitivos de férias, com crédito automático de
dias e expiração.

RESUMO TÉCNICO:
- `rh_dados_funcionais.inicio_aquisitivo_dia`/`_mes`: início do período
  aquisitivo (só dia e mês; repete todo ano), validado por CHECK.
- `rh_periodos_aquisitivos`: um registro por período de 12 meses, com dias
  creditados, origem (automático ou ajuste da CGP) e expiração.
- `rh_afastamentos.periodo_aquisitivo_id`: período cujo saldo as férias
  debitam.
- `rh_parametros`: dias por período (30), folga do aviso de expiração (15) e
  aviso ativo.

FINALIDADE DE NEGÓCIO:
Período aquisitivo é o ciclo de 12 meses de trabalho que dá direito a dias de
férias. O controle automático mostra o saldo de cada servidor e avisa antes de
os dias expirarem; a CGP (Coordenadoria de Gestão de Pessoas) pode ajustar.

CONTEXTO NO SISTEMA:
Tabelas do Módulo RH (`rh_dados_funcionais`, `rh_afastamentos`,
`rh_parametros`, criadas em `6be74b4141cb`) e `usuarios`; serviços de férias em
`app/services/rh/`.

Revision ID: 5de0447b97ad
Revises: 6be74b4141cb
Create Date: 2026-09-29 15:00:00

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "5de0447b97ad"
down_revision: str | Sequence[str] | None = "6be74b4141cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# CHECK do início do período: dia e mês ficam ambos nulos ou formam uma data
# possível (fevereiro aceita 29 porque o dia se repete em anos bissextos).
CK_INICIO = (
    "(inicio_aquisitivo_dia IS NULL AND inicio_aquisitivo_mes IS NULL) OR "
    "(inicio_aquisitivo_mes BETWEEN 1 AND 12 AND inicio_aquisitivo_dia BETWEEN 1 AND "
    "CASE WHEN inicio_aquisitivo_mes = 2 THEN 29 WHEN inicio_aquisitivo_mes IN (4, 6, 9, 11) THEN 30 ELSE 31 END)"
)


# upgrade() aplica esta mudança no banco (alembic upgrade) e downgrade() a
# desfaz (alembic downgrade), voltando à revisão anterior.
#
# As funções op.* do Alembic executam comandos de estrutura (DDL) no banco:
# create_table, add_column, alter_column, create_index, drop_* etc.
#
# server_default é o valor padrão gravado pelo próprio banco; serve também para
# preencher as linhas que já existiam quando a coluna é criada.
def upgrade() -> None:
    """Cria a tabela de períodos, as colunas novas (com FK e CHECK) e os
    parâmetros, já com os valores iniciais via server_default.
    """
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
    """Remove parâmetros, restrições, colunas e a tabela de períodos. Os saldos
    de férias calculados se perdem.
    """
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
