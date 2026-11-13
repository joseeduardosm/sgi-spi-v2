# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a diferença retroativa informada manualmente e levar os créditos de reajuste para o fundo.

"""contratos: diferença retroativa manual e créditos em fundo

- `contratos_diferencas_manuais`: valor total (com sinal), justificativa, PDF da memória, quem informou e quando; uma por reajuste ou repactuação.
- `contratos_diferencas_manuais_competencias`: os meses (competências) cobertos, que ficam travados no preço de antes.
- `contratos_competencias.diferenca_manual_id`: a competência complementar gerada pela diferença manual positiva.
- `contratos_abatimentos_reajuste.diferenca_manual_id`: o crédito que veio de uma diferença manual negativa.
- Dados: os créditos que estavam presos a uma competência com a medição ainda aberta voltam para o fundo (`competencia_id` nulo);
  daqui em diante o gestor é quem aplica cada crédito numa medição.

Revision ID: e2a4c6e8f0b1
Revises: d1f3a5b7c9e2
Create Date: 2026-11-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e2a4c6e8f0b1"
down_revision: str | Sequence[str] | None = "d1f3a5b7c9e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contratos_diferencas_manuais",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("contrato_id", sa.Uuid(), sa.ForeignKey("contratos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("reajuste_id", sa.Uuid(), sa.ForeignKey("contratos_reajustes.id", ondelete="CASCADE"), unique=True),
        sa.Column("repactuacao_id", sa.Uuid(), sa.ForeignKey("contratos_repactuacoes.id", ondelete="CASCADE"), unique=True),
        sa.Column("valor", sa.Numeric(18, 2), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.Column("anexo_id", sa.Uuid(), sa.ForeignKey("anexos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("informado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("informado_por_nome", sa.String(250), nullable=False),
        sa.Column("informado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("(reajuste_id IS NULL) <> (repactuacao_id IS NULL)", name="ck_contratos_diferencas_manuais_origem"),
        sa.CheckConstraint("valor <> 0", name="ck_contratos_diferencas_manuais_valor"),
    )
    op.create_table(
        "contratos_diferencas_manuais_competencias",
        sa.Column("diferenca_manual_id", sa.Uuid(), sa.ForeignKey("contratos_diferencas_manuais.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("competencia_id", sa.Uuid(), sa.ForeignKey("contratos_competencias.id", ondelete="CASCADE"), primary_key=True, index=True),
    )
    op.add_column("contratos_competencias", sa.Column("diferenca_manual_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_contratos_competencias_diferenca_manual", "contratos_competencias", "contratos_diferencas_manuais",
                          ["diferenca_manual_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_contratos_competencias_diferenca_manual_id", "contratos_competencias", ["diferenca_manual_id"])
    op.add_column("contratos_abatimentos_reajuste", sa.Column("diferenca_manual_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_contratos_abatimentos_reajuste_diferenca_manual", "contratos_abatimentos_reajuste", "contratos_diferencas_manuais",
                          ["diferenca_manual_id"], ["id"], ondelete="SET NULL")
    # Créditos presos a uma medição ainda aberta voltam ao fundo: o gestor decide onde aplicar
    op.execute(
        "UPDATE contratos_abatimentos_reajuste SET competencia_id = NULL "
        "WHERE competencia_id IN (SELECT id FROM contratos_competencias WHERE medicao_concluida_em IS NULL)"
    )


def downgrade() -> None:
    op.drop_constraint("fk_contratos_abatimentos_reajuste_diferenca_manual", "contratos_abatimentos_reajuste", type_="foreignkey")
    op.drop_column("contratos_abatimentos_reajuste", "diferenca_manual_id")
    op.drop_index("ix_contratos_competencias_diferenca_manual_id", table_name="contratos_competencias")
    op.drop_constraint("fk_contratos_competencias_diferenca_manual", "contratos_competencias", type_="foreignkey")
    op.drop_column("contratos_competencias", "diferenca_manual_id")
    op.drop_table("contratos_diferencas_manuais_competencias")
    op.drop_table("contratos_diferencas_manuais")
