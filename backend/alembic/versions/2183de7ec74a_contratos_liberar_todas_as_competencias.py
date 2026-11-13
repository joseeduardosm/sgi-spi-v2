"""
===============================================================================
ARQUIVO: 2183de7ec74a_contratos_liberar_todas_as_competencias.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Criar no contrato a opção "Liberar todas as competências".

RESUMO TÉCNICO:
Acrescenta a coluna booleana `contratos.liberar_todas_competencias`, não nula,
com padrão `false` no banco (os contratos existentes ficam com a opção
desligada).

FINALIDADE DE NEGÓCIO:
Competência é o mês de execução do contrato que será medido e pago. Normalmente
as competências são liberadas aos poucos; a opção permite deixar todas
disponíveis de uma vez, por exemplo para lançar o histórico de um contrato
antigo.

CONTEXTO NO SISTEMA:
Tabela `contratos` (modelo em `app/models/contratos/contrato.py`); a regra de
liberação fica no serviço de competências
(`app/services/contratos/servico_competencias.py`).

Revision ID: 2183de7ec74a
Revises: e5b8c3d7a921
Create Date: 2026-10-02 18:28:26.654600

===============================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Identificação da migração: esta revisão (revision) e a anterior (down_revision)
revision: str = '2183de7ec74a'
down_revision: Union[str, Sequence[str], None] = 'e5b8c3d7a921'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# upgrade() aplica esta mudança no banco (alembic upgrade) e downgrade() a
# desfaz (alembic downgrade), voltando à revisão anterior.
#
# As funções op.* do Alembic executam comandos de estrutura (DDL) no banco:
# create_table, add_column, alter_column, create_index, drop_* etc.
#
# server_default é o valor padrão gravado pelo próprio banco; serve também para
# preencher as linhas que já existiam quando a coluna é criada.
def upgrade() -> None:
    """Cria a coluna `liberar_todas_competencias` (padrão falso)."""
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.add_column('contratos', sa.Column('liberar_todas_competencias', sa.Boolean(), server_default='false', nullable=False))
    # Fim dos comandos gerados pelo autogenerate


def downgrade() -> None:
    """Remove a coluna; a opção deixa de existir."""
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.drop_column('contratos', 'liberar_todas_competencias')
    # Fim dos comandos gerados pelo autogenerate
