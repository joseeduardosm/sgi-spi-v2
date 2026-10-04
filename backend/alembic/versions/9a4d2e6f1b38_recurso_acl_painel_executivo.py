# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar o recurso `painel-executivo` na ACL (sem regras: só o SuperRoot acessa até a Diretoria receber a regra).
"""recurso ACL painel-executivo

Revision ID: 9a4d2e6f1b38
Revises: 7c1e9a3b5d20
Create Date: 2026-10-03 23:10:00
"""
from typing import Sequence, Union

from alembic import op

revision: str = '9a4d2e6f1b38'
down_revision: Union[str, Sequence[str], None] = '7c1e9a3b5d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
               "SELECT 'Painel Executivo', 'painel-executivo', 'Painéis e gráficos da Diretoria (contratos, RH e tarefas). Sem regras, só o SuperRoot vê.', "
               "'/painel-executivo', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
               "WHERE NOT EXISTS (SELECT 1 FROM acl_recursos WHERE slug = 'painel-executivo')")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM acl_recursos WHERE slug = 'painel-executivo'")
