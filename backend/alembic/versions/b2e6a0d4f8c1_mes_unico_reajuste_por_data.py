# Criado por José Eduardo Santana Martins
# Este arquivo serve para preparar o banco para o reajuste por data, o mês da virada como uma medição só e o corte de alertas por contrato.
"""contratos: reajuste com data de efeito, itens da medição por trecho do mês e corte de alertas por contrato

Revision ID: b2e6a0d4f8c1
Revises: a1d4f8c2e6b9
Create Date: 2026-10-06 23:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b2e6a0d4f8c1"
down_revision: str | Sequence[str] | None = "a1d4f8c2e6b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reajuste ganha `data_efeito`; cada linha da medição passa a ter trecho; contrato ganha `alertas_a_partir_de`."""
    # Reajuste: a data de efeito dos reajustes existentes é o dia 1 do mês de referência (o mesmo efeito de antes)
    op.add_column("contratos_reajustes", sa.Column("data_efeito", sa.Date(), nullable=True))
    op.execute("UPDATE contratos_reajustes SET data_efeito = mes_referencia")

    # Itens da medição: um trecho por linha (mês sem virada = trecho 1, sem datas)
    op.add_column("contratos_competencias_itens", sa.Column("segmento", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("contratos_competencias_itens", sa.Column("periodo_inicio", sa.Date(), nullable=True))
    op.add_column("contratos_competencias_itens", sa.Column("periodo_fim", sa.Date(), nullable=True))
    op.add_column("contratos_competencias_itens", sa.Column("periodo_rotulo", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("contratos_competencias_itens", sa.Column("sequencia_vigencia", sa.Integer(), nullable=True))
    op.drop_constraint("contratos_competencias_itens_competencia_id_item_id_key", "contratos_competencias_itens", type_="unique")
    op.create_unique_constraint("uq_contratos_competencias_itens_trecho", "contratos_competencias_itens", ["competencia_id", "item_id", "segmento"])

    # Contrato: corte de alertas próprio
    op.add_column("contratos", sa.Column("alertas_a_partir_de", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("contratos", "alertas_a_partir_de")
    op.drop_constraint("uq_contratos_competencias_itens_trecho", "contratos_competencias_itens", type_="unique")
    # Só uma linha por item e competência pode voltar: as linhas de trechos seguintes são descartadas
    op.execute("DELETE FROM contratos_competencias_itens WHERE segmento > 1")
    op.create_unique_constraint("contratos_competencias_itens_competencia_id_item_id_key", "contratos_competencias_itens", ["competencia_id", "item_id"])
    for coluna in ("sequencia_vigencia", "periodo_rotulo", "periodo_fim", "periodo_inicio", "segmento"):
        op.drop_column("contratos_competencias_itens", coluna)
    op.drop_column("contratos_reajustes", "data_efeito")
