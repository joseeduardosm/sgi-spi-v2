"""
===============================================================================
ARQUIVO: f2b8d4a6c1e3_reajuste_calculo_mes_quebrado.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que troca a lista de meses integrais do reajuste por uma
escolha única (pro rata ou integral) para todos os meses quebrados.

RESUMO TÉCNICO:
Cria contratos_reajustes.calculo_mes_quebrado (texto, nulo = ainda não
escolhido), marca como "integral" os reajustes que tinham algum mês na lista
meses_integrais e apaga essa coluna JSONB. O downgrade recria meses_integrais
vazia e apaga a coluna nova.

FINALIDADE DE NEGÓCIO:
Reajuste é a atualização do preço do contrato por índice. A forma de calcular
os meses quebrados pela data de efeito passa a ser uma só para o reajuste
inteiro; os reajustes sem mês marcado ficam sem escolha e o gestor escolhe na
tela.

CONTEXTO NO SISTEMA:
Tabela contratos_reajustes; serviço app/services/contratos/servico_reajuste.py
e rotas de alterações contratuais. Aplicada com 'alembic upgrade head' (o
instalador e a atualização do sistema rodam esse comando).

Revision ID: f2b8d4a6c1e3
Revises: e4c7a9b2d6f1
Create Date: 2026-10-29

===============================================================================
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# ────────────────────────────────────────────────────────────────────────────
revision = "f2b8d4a6c1e3"
down_revision = "e4c7a9b2d6f1"
branch_labels = None
depends_on = None
# ────────────────────────────────────────────────────────────────────────────


def upgrade() -> None:
    """Cria calculo_mes_quebrado, converte os dados antigos e apaga meses_integrais."""
    # Mês quebrado: mês em que a data de efeito do reajuste cai no meio, e o valor
    # pode ser proporcional aos dias (pro rata) ou cheio (integral).
    op.add_column(
        "contratos_reajustes",
        sa.Column(
            "calculo_mes_quebrado",
            sa.String(10),
            nullable=True,
            comment='Cálculo dos meses quebrados pela data de efeito: "pro_rata" ou "integral"; nulo = ainda não escolhido.',
        ),
    )
    # Quem tinha ao menos um mês integral na lista antiga passa a "integral"; o resto fica nulo
    op.execute("UPDATE contratos_reajustes SET calculo_mes_quebrado = 'integral' WHERE jsonb_array_length(meses_integrais) > 0")
    op.drop_column("contratos_reajustes", "meses_integrais")


def downgrade() -> None:
    """Recria meses_integrais vazia (a escolha feita não é convertida de volta)."""
    op.add_column(
        "contratos_reajustes",
        sa.Column("meses_integrais", JSONB(), nullable=False, server_default="[]"),
    )
    op.drop_column("contratos_reajustes", "calculo_mes_quebrado")
