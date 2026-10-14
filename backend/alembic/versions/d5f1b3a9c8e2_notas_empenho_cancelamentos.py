# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela das NEs de cancelamento (abatem o saldo de uma NE original).
"""contratos: NEs de cancelamento

`contratos_notas_empenho_cancelamentos`: número próprio (único no contrato), valor (parcial ou total) e justificativa; abate o saldo da NE original.

Revision ID: d5f1b3a9c8e2
Revises: c4e8a2f6d1b7
Create Date: 2026-10-13 23:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd5f1b3a9c8e2'
down_revision: Union[str, Sequence[str], None] = 'c4e8a2f6d1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'contratos_notas_empenho_cancelamentos',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('contrato_id', sa.Uuid(), nullable=False),
        sa.Column('nota_id', sa.Uuid(), nullable=False),
        sa.Column('numero', sa.String(30), nullable=False),
        sa.Column('valor', sa.Numeric(18, 2), nullable=False),
        sa.Column('justificativa', sa.String(2000), nullable=False, server_default=''),
        sa.Column('criado_por_id', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['contrato_id'], ['contratos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['nota_id'], ['contratos_notas_empenho.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['criado_por_id'], ['usuarios.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contrato_id', 'numero'),
    )
    op.create_index('ix_contratos_notas_empenho_cancelamentos_contrato_id', 'contratos_notas_empenho_cancelamentos', ['contrato_id'])
    op.create_index('ix_contratos_notas_empenho_cancelamentos_nota_id', 'contratos_notas_empenho_cancelamentos', ['nota_id'])


def downgrade() -> None:
    op.drop_table('contratos_notas_empenho_cancelamentos')
