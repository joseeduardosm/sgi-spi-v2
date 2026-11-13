"""
===============================================================================
ARQUIVO: f6b9d4e8a3c2_usuario_tema.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que cria a coluna que guarda o tema da interface (claro,
escuro ou automático) de cada usuário.

RESUMO TÉCNICO:
Cria usuarios.tema (texto de até 10 caracteres, padrão 'auto', não nulo); os
usuários existentes começam em 'auto'. O downgrade remove a coluna.

FINALIDADE DE NEGÓCIO:
Cada pessoa escolhe se o SGI aparece claro, escuro ou seguindo o tema do
sistema operacional, e a escolha a acompanha em qualquer computador.

CONTEXTO NO SISTEMA:
Tabela usuarios; lida e gravada pelas preferências do usuário e aplicada pelo
frontend Angular. Aplicada com 'alembic upgrade head' (o instalador e a
atualização do sistema rodam esse comando).

Revision ID: f6b9d4e8a3c2
Revises: e5a8c3d7f2b1
Create Date: 2026-10-04 12:00:00

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f6b9d4e8a3c2"
down_revision: str | Sequence[str] | None = "e5a8c3d7f2b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Todos os usuários existentes começam em `auto` (seguem o tema do sistema operacional)."""
    op.add_column("usuarios", sa.Column("tema", sa.String(length=10), server_default="auto", nullable=False))


def downgrade() -> None:
    """Remove a coluna."""
    op.drop_column("usuarios", "tema")
