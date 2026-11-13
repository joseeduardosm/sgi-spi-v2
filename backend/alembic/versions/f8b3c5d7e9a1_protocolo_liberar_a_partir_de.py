"""
===============================================================================
ARQUIVO: f8b3c5d7e9a1_protocolo_liberar_a_partir_de.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que acrescenta o campo "liberar a partir de" às sequências do
Protocolo (faixa reservada ao Serviço de Apoio Administrativo, SAA).

RESUMO TÉCNICO:
Cria protocolo_sequencias.liberar_a_partir_de (inteiro opcional) e a check
constraint que exige o valor entre o início e o fim + 1 da sequência. As
sequências existentes continuam sem faixa reservada. O downgrade remove as duas
coisas.

FINALIDADE DE NEGÓCIO:
Na numeração de documentos do Protocolo, os primeiros números de uma sequência
podem ficar reservados ao SAA; os demais setores só recebem números a partir do
valor informado.

CONTEXTO NO SISTEMA:
Tabela protocolo_sequencias; serviço app/services/servico_protocolo.py e rotas
app/api/routes/protocolo.py. Aplicada com 'alembic upgrade head' (o instalador
e a atualização do sistema rodam esse comando).

Revision ID: f8b3c5d7e9a1
Revises: e7a2b4d6f8c1
Create Date: 2026-10-09 20:00:00

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f8b3c5d7e9a1"
down_revision: str | Sequence[str] | None = "e7a2b4d6f8c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Coluna opcional: as sequências existentes continuam sem faixa reservada."""
    op.add_column("protocolo_sequencias", sa.Column("liberar_a_partir_de", sa.Integer(), nullable=True))
    # A faixa precisa caber dentro da sequência: entre o início e o fim + 1
    # (fim + 1 significa "nenhum número liberado para os demais setores")
    op.create_check_constraint(
        "ck_protocolo_sequencias_liberar", "protocolo_sequencias",
        "liberar_a_partir_de IS NULL OR (liberar_a_partir_de >= inicio AND liberar_a_partir_de <= fim + 1)")


def downgrade() -> None:
    """Remove a restrição e a coluna da faixa reservada."""
    op.drop_constraint("ck_protocolo_sequencias_liberar", "protocolo_sequencias", type_="check")
    op.drop_column("protocolo_sequencias", "liberar_a_partir_de")
