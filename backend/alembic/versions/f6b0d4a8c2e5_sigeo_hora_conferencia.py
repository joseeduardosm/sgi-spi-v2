"""
===============================================================================
ARQUIVO: f6b0d4a8c2e5_sigeo_hora_conferencia.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que torna parametrizável a hora da conferência diária das OBs
no SIGEO (padrão 8 horas).

RESUMO TÉCNICO:
Cria a coluna integracao_sigeo.hora_conferencia (inteiro, não nulo, padrão 8).
O downgrade remove a coluna.

FINALIDADE DE NEGÓCIO:
SIGEO é o sistema de execução orçamentária consultado pelo SGI para conferir se
as Ordens Bancárias (OB) dos contratos foram pagas. O administrador pode
escolher a hora em que essa conferência automática roda a cada dia.

CONTEXTO NO SISTEMA:
Tabela integracao_sigeo; rotas app/api/routes/integracao_sigeo.py e a tarefa
agendada que faz a conferência. Aplicada com 'alembic upgrade head' (o
instalador e a atualização do sistema rodam esse comando).

Revision ID: f6b0d4a8c2e5
Revises: e5a9c3f7b1d4
Create Date: 2026-10-26

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f6b0d4a8c2e5"
down_revision: str | Sequence[str] | None = "e5a9c3f7b1d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria integracao_sigeo.hora_conferencia; o server_default "8" preenche a linha existente."""
    op.add_column("integracao_sigeo", sa.Column("hora_conferencia", sa.Integer(), nullable=False, server_default="8"))


def downgrade() -> None:
    """Remove a coluna da hora da conferência."""
    op.drop_column("integracao_sigeo", "hora_conferencia")
