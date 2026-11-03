# Criado por José Eduardo Santana Martins
# Este arquivo serve para marcar como "ligada" toda porta que tem algo ligado (regra: porta com equipamento está necessariamente ligada).

"""rede: porta com ligação fica com status "ligada"

Na carga por LLDP, as portas dos access points, dos Dell e do 3Com (equipamentos não lidos por SSH) ficaram sem status, embora o LLDP só
enxergue cabo ativo. Esta migração passa a `up` toda porta que está numa conexão (de qualquer lado). Só dados, sem mudar a estrutura.

Revision ID: f4b6d8e0a2c3
Revises: e2a4c6e8b0d1
Create Date: 2026-11-03
"""
from collections.abc import Sequence

from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f4b6d8e0a2c3"
down_revision: str | Sequence[str] | None = "e2a4c6e8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Toda porta numa conexão passa a "ligada"."""
    op.execute("""
        UPDATE rede_portas SET status = 'up'
        WHERE (status IS NULL OR status <> 'up')
          AND id IN (SELECT porta_a_id FROM rede_conexoes UNION SELECT porta_b_id FROM rede_conexoes WHERE porta_b_id IS NOT NULL)
    """)


def downgrade() -> None:
    """Sem volta: o status anterior (vazio) não foi guardado e não faz falta."""
