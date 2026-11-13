"""
===============================================================================
ARQUIVO: 3f23277d8a5a_contratos_valor_unitario_com_4_casas.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Ampliar o preço unitário dos itens (contrato, medição, reajuste e aditamento)
para 4 casas decimais, como R$ 0,075 por página.

RESUMO TÉCNICO:
Só altera o tipo das colunas de NUMERIC(18,2) para NUMERIC(18,4) em
`contratos_itens`, `contratos_competencias_itens`, `contratos_alteracoes_itens`
e `contratos_reajustes_itens`; nenhum valor muda. Os totais em reais continuam
com 2 casas. O downgrade arredonda os preços para 2 casas (perde precisão).

FINALIDADE DE NEGÓCIO:
Há contratos com preço unitário de frações de centavo (impressão por página,
por exemplo). Sem as 4 casas, o valor seria arredondado e a medição mensal
ficaria diferente do contratado.

CONTEXTO NO SISTEMA:
Tabelas de itens do módulo Contratos (cadastro, medição/competências,
aditamentos e reajustes) e seus modelos em `app/models/contratos/`.

Revision ID: 3f23277d8a5a
Revises: 11d8a496ccab
Create Date: 2026-10-01 17:55:59.095627

===============================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Identificação da migração: esta revisão (revision) e a anterior (down_revision)
revision: str = '3f23277d8a5a'
down_revision: Union[str, Sequence[str], None] = '11d8a496ccab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# upgrade() aplica esta mudança no banco (alembic upgrade) e downgrade() a
# desfaz (alembic downgrade), voltando à revisão anterior.
#
# As funções op.* do Alembic executam comandos de estrutura (DDL) no banco:
# create_table, add_column, alter_column, create_index, drop_* etc.
def upgrade() -> None:
    """Amplia `valor_unitario` (e os valores do reajuste) para 4 casas
    decimais. `existing_type` informa o tipo atual para o Alembic gerar o
    ALTER correto.
    """
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.alter_column('contratos_alteracoes_itens', 'valor_unitario',
               existing_type=sa.NUMERIC(precision=18, scale=2),
               type_=sa.Numeric(precision=18, scale=4),
               existing_nullable=False)
    op.alter_column('contratos_competencias_itens', 'valor_unitario',
               existing_type=sa.NUMERIC(precision=18, scale=2),
               type_=sa.Numeric(precision=18, scale=4),
               existing_nullable=False)
    op.alter_column('contratos_itens', 'valor_unitario',
               existing_type=sa.NUMERIC(precision=18, scale=2),
               type_=sa.Numeric(precision=18, scale=4),
               existing_nullable=False)
    op.alter_column('contratos_reajustes_itens', 'valor_unitario_atual',
               existing_type=sa.NUMERIC(precision=18, scale=2),
               type_=sa.Numeric(precision=18, scale=4),
               existing_nullable=False)
    op.alter_column('contratos_reajustes_itens', 'valor_referencial',
               existing_type=sa.NUMERIC(precision=18, scale=2),
               type_=sa.Numeric(precision=18, scale=4),
               existing_nullable=True)
    op.alter_column('contratos_reajustes_itens', 'valor_unitario_reajustado',
               existing_type=sa.NUMERIC(precision=18, scale=2),
               type_=sa.Numeric(precision=18, scale=4),
               existing_nullable=False)
    # Fim dos comandos gerados pelo autogenerate


def downgrade() -> None:
    """Volta as colunas para 2 casas decimais; o banco arredonda os preços."""
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.alter_column('contratos_reajustes_itens', 'valor_unitario_reajustado',
               existing_type=sa.Numeric(precision=18, scale=4),
               type_=sa.NUMERIC(precision=18, scale=2),
               existing_nullable=False)
    op.alter_column('contratos_reajustes_itens', 'valor_referencial',
               existing_type=sa.Numeric(precision=18, scale=4),
               type_=sa.NUMERIC(precision=18, scale=2),
               existing_nullable=True)
    op.alter_column('contratos_reajustes_itens', 'valor_unitario_atual',
               existing_type=sa.Numeric(precision=18, scale=4),
               type_=sa.NUMERIC(precision=18, scale=2),
               existing_nullable=False)
    op.alter_column('contratos_itens', 'valor_unitario',
               existing_type=sa.Numeric(precision=18, scale=4),
               type_=sa.NUMERIC(precision=18, scale=2),
               existing_nullable=False)
    op.alter_column('contratos_competencias_itens', 'valor_unitario',
               existing_type=sa.Numeric(precision=18, scale=4),
               type_=sa.NUMERIC(precision=18, scale=2),
               existing_nullable=False)
    op.alter_column('contratos_alteracoes_itens', 'valor_unitario',
               existing_type=sa.Numeric(precision=18, scale=4),
               type_=sa.NUMERIC(precision=18, scale=2),
               existing_nullable=False)
    # Fim dos comandos gerados pelo autogenerate
