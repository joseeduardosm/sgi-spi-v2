"""
===============================================================================
ARQUIVO: 46921c091299_contratos_numero_livre.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Permitir que o número do contrato seja digitado em formato livre, e não apenas
como NNN/AAAA.

RESUMO TÉCNICO:
- Nova coluna `contratos.numero` (texto até 60), preenchida nos contratos
  existentes com o formato antigo (`012/2026`), e índice único por
  `lower(numero)` (não aceita o mesmo número com maiúsculas diferentes).
- `sequencial` e `ano` passam a ser opcionais (só preenchidos quando o número
  segue NNN/AAAA) e deixam de ser únicos em conjunto.

FINALIDADE DE NEGÓCIO:
Contratos de outros órgãos, atas e instrumentos antigos usam numerações
variadas; o número livre permite cadastrá-los como aparecem nos documentos
oficiais, sem impedir números duplicados por acidente.

CONTEXTO NO SISTEMA:
Tabela `contratos` (modelo `app/models/contratos/contrato.py`), usada nas telas
e buscas de contratos e nos documentos gerados.

Revision ID: 46921c091299
Revises: 0ecc10bd1805
Create Date: 2026-09-28 21:20:00

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "46921c091299"
down_revision: str | Sequence[str] | None = "0ecc10bd1805"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# upgrade() aplica esta mudança no banco (alembic upgrade) e downgrade() a
# desfaz (alembic downgrade), voltando à revisão anterior.
#
# As funções op.* do Alembic executam comandos de estrutura (DDL) no banco:
# create_table, add_column, alter_column, create_index, drop_* etc.
#
# op.execute() roda um comando SQL escrito à mão, em geral para ajustar ou
# semear dados.
def upgrade() -> None:
    """Cria e preenche o número livre e afrouxa sequencial/ano.

    A coluna nasce opcional, recebe o número montado com lpad (zeros à
    esquerda) e só depois vira obrigatória: assim as linhas antigas não
    quebram a restrição NOT NULL.
    """
    op.add_column("contratos", sa.Column("numero", sa.String(length=60), nullable=True))
    op.execute("UPDATE contratos SET numero = lpad(sequencial::text, 3, '0') || '/' || lpad(ano::text, 4, '0')")
    op.alter_column("contratos", "numero", existing_type=sa.String(length=60), nullable=False)
    # Índice único sobre uma expressão (lower) para a unicidade não depender de
    # maiúsculas e minúsculas.
    op.create_index("ux_contratos_numero", "contratos", [sa.text("lower(numero)")], unique=True)
    op.drop_constraint("contratos_sequencial_ano_key", "contratos", type_="unique")
    op.alter_column("contratos", "sequencial", existing_type=sa.Integer(), nullable=True)
    op.alter_column("contratos", "ano", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Volta ao número NNN/AAAA.

    Falha se houver contrato com número fora desse padrão (sequencial ou ano
    nulos), pois as colunas voltam a ser obrigatórias.
    """
    op.alter_column("contratos", "ano", existing_type=sa.Integer(), nullable=False)
    op.alter_column("contratos", "sequencial", existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint("contratos_sequencial_ano_key", "contratos", ["sequencial", "ano"])
    op.drop_index("ux_contratos_numero", table_name="contratos")
    op.drop_column("contratos", "numero")
