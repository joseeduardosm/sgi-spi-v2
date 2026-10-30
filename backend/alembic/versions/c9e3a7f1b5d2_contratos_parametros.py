# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela dos parâmetros do módulo de contratos, já com os valores que valiam no código.

"""contratos: tabela de parâmetros (linha única)

Revision ID: c9e3a7f1b5d2
Revises: b8d2f6a0c4e7
Create Date: 2026-10-27
"""
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "c9e3a7f1b5d2"
down_revision: str | Sequence[str] | None = "b8d2f6a0c4e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mesmos valores de `app.models.contratos.parametros.PADROES` na data desta migração (a migração não importa o modelo para não mudar com ele)
INICIAIS = {
    "corte_alertas_a_partir_de": date(2026, 9, 1), "corte_marcadores_a_partir_de": date(2026, 8, 1), "dias_pagamento_vencendo": 5, "dias_atraso": 30,
    "dias_vigencia_a_vencer": 90, "dias_vigencia_atencao": 180, "dias_sem_prorrogacao_alto": 60, "dias_documento_alto": 15, "dias_documento_medio": 30,
    "dias_fim_vigencia_alto": 30, "dias_fim_vigencia_medio": 60, "vigencia_maxima_padrao_meses": 60, "maximo_meses_vigencia_retroativa": 120,
    "limite_aditamento_sem_autorizacao": 25, "limite_acerto_centavos": 1, "maximo_notas_fiscais": 20, "prazo_pagamento_padrao_dias": 30,
    "prazo_nota_fiscal_horas": 48, "xml_tamanho_maximo_mb": 5, "planilha_tamanho_maximo_mb": 5, "maximo_anexos_ocorrencia": 5, "anexos_email_maximo_mb": 15,
}


def upgrade() -> None:
    tabela = op.create_table(
        "contratos_parametros",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("corte_alertas_a_partir_de", sa.Date(), nullable=False),
        sa.Column("corte_marcadores_a_partir_de", sa.Date(), nullable=False),
        sa.Column("dias_pagamento_vencendo", sa.Integer(), nullable=False),
        sa.Column("dias_atraso", sa.Integer(), nullable=False),
        sa.Column("dias_vigencia_a_vencer", sa.Integer(), nullable=False),
        sa.Column("dias_vigencia_atencao", sa.Integer(), nullable=False),
        sa.Column("dias_sem_prorrogacao_alto", sa.Integer(), nullable=False),
        sa.Column("dias_documento_alto", sa.Integer(), nullable=False),
        sa.Column("dias_documento_medio", sa.Integer(), nullable=False),
        sa.Column("dias_fim_vigencia_alto", sa.Integer(), nullable=False),
        sa.Column("dias_fim_vigencia_medio", sa.Integer(), nullable=False),
        sa.Column("vigencia_maxima_padrao_meses", sa.Integer(), nullable=False),
        sa.Column("maximo_meses_vigencia_retroativa", sa.Integer(), nullable=False),
        sa.Column("limite_aditamento_sem_autorizacao", sa.Numeric(7, 2), nullable=False),
        sa.Column("limite_acerto_centavos", sa.Numeric(10, 2), nullable=False),
        sa.Column("maximo_notas_fiscais", sa.Integer(), nullable=False),
        sa.Column("prazo_pagamento_padrao_dias", sa.Integer(), nullable=False),
        sa.Column("prazo_nota_fiscal_horas", sa.Integer(), nullable=False),
        sa.Column("xml_tamanho_maximo_mb", sa.Integer(), nullable=False),
        sa.Column("planilha_tamanho_maximo_mb", sa.Integer(), nullable=False),
        sa.Column("maximo_anexos_ocorrencia", sa.Integer(), nullable=False),
        sa.Column("anexos_email_maximo_mb", sa.Integer(), nullable=False),
        sa.Column("atualizado_por_nome", sa.String(length=250), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
    )
    # Linha única com os valores de hoje: nada muda de comportamento até alguém editar
    op.bulk_insert(tabela, [{"id": 1, **INICIAIS}])


def downgrade() -> None:
    op.drop_table("contratos_parametros")
