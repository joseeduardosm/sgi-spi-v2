"""
===============================================================================
ARQUIVO: 0ecc10bd1805_reajuste_desconto_abatimentos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Preparar o banco para o reajuste com desconto (índice negativo): gravar a
diferença retroativa do reajuste e registrar os abatimentos do crédito da SPI
nas próximas competências.

RESUMO TÉCNICO:
- `contratos_reajustes.diferenca_retroativa`: diferença líquida das
  competências já medidas, gravada na conclusão do reajuste (> 0 gera a
  competência de diferença; < 0 vira crédito da SPI).
- `contratos_abatimentos_reajuste`: partes do crédito abatidas no valor
  autorizado das próximas competências (`competencia_id` nulo = crédito ainda
  pendente; `origem_id` liga a parte ao crédito de onde saiu). Valor >= 0.

FINALIDADE DE NEGÓCIO:
Quando o reajuste reduz o preço com efeito retroativo, a empresa recebeu a
mais nos meses já pagos. O sistema guarda esse crédito e o desconta das
próximas competências (meses de execução do contrato), sem conta manual.

CONTEXTO NO SISTEMA:
Relaciona-se com `contratos`, `contratos_reajustes` e
`contratos_competencias`; usado pelo serviço de reajuste
(`app/services/contratos/servico_reajuste.py`) e pela tela de execução.

Revision ID: 0ecc10bd1805
Revises: e5a8c3d1f2b4
Create Date: 2026-09-28 14:07:53

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "0ecc10bd1805"
down_revision: str | Sequence[str] | None = "e5a8c3d1f2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELA = "contratos_abatimentos_reajuste"


# O módulo `op` do Alembic traz as operações de esquema (create_table,
# add_column, create_index, drop_* etc.); cada uma vira um comando SQL
# executado no banco.
def upgrade() -> None:
    """Cria a tabela de abatimentos (com chaves estrangeiras e índices) e a
    coluna `diferenca_retroativa` em `contratos_reajustes` (nula nos reajustes
    antigos).
    """
    op.create_table(
        TABELA,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contrato_id", sa.Uuid(), nullable=False),
        sa.Column("reajuste_id", sa.Uuid(), nullable=False),
        sa.Column("competencia_id", sa.Uuid(), nullable=True),
        sa.Column("origem_id", sa.Uuid(), nullable=True),
        sa.Column("valor", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("valor >= 0", name="ck_contratos_abatimentos_reajuste_valor"),
        sa.ForeignKeyConstraint(["competencia_id"], ["contratos_competencias.id"], ondelete="SET NULL",
                                name="contratos_abatimentos_reajuste_competencia_id_fkey"),
        sa.ForeignKeyConstraint(["contrato_id"], ["contratos.id"], ondelete="CASCADE", name="contratos_abatimentos_reajuste_contrato_id_fkey"),
        # Autorreferência: a parte abatida aponta para o crédito original na
        # mesma tabela.
        sa.ForeignKeyConstraint(["origem_id"], [f"{TABELA}.id"], ondelete="SET NULL", name="contratos_abatimentos_reajuste_origem_id_fkey"),
        sa.ForeignKeyConstraint(["reajuste_id"], ["contratos_reajustes.id"], ondelete="CASCADE", name="contratos_abatimentos_reajuste_reajuste_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="contratos_abatimentos_reajuste_pkey"),
    )
    # Um índice por chave estrangeira, para as consultas por contrato, reajuste
    # e competência.
    for coluna in ("competencia_id", "contrato_id", "reajuste_id"):
        op.create_index(f"ix_{TABELA}_{coluna}", TABELA, [coluna], unique=False)
    op.add_column("contratos_reajustes", sa.Column("diferenca_retroativa", sa.Numeric(precision=18, scale=2), nullable=True))


def downgrade() -> None:
    """Remove a coluna e a tabela, na ordem inversa da criação (índices antes
    da tabela). Os créditos registrados se perdem.
    """
    op.drop_column("contratos_reajustes", "diferenca_retroativa")
    for coluna in ("reajuste_id", "contrato_id", "competencia_id"):
        op.drop_index(f"ix_{TABELA}_{coluna}", table_name=TABELA)
    op.drop_table(TABELA)
