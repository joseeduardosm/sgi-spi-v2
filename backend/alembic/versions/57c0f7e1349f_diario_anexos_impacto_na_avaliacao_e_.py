# Criado por José Eduardo Santana Martins
# Este arquivo serve para acrescentar anexos e impacto na avaliação às ocorrências do diário e o resultado do e-mail da avaliação.
"""diário: anexos e itens de avaliação impactados; avaliação: resultado do e-mail à contratada

Revision ID: 57c0f7e1349f
Revises: aef1af3a69ff
Create Date: 2026-09-30 21:07:18.519506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '57c0f7e1349f'
down_revision: Union[str, Sequence[str], None] = 'aef1af3a69ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('contratos_diario_anexos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ocorrencia_id', sa.Uuid(), nullable=False),
    sa.Column('anexo_id', sa.Uuid(), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['anexo_id'], ['anexos.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['ocorrencia_id'], ['contratos_diario_ocorrencias.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contratos_diario_anexos_ocorrencia_id'), 'contratos_diario_anexos', ['ocorrencia_id'], unique=False)
    op.create_table('contratos_diario_itens_avaliacao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ocorrencia_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.String(length=64), nullable=False),
    sa.Column('item_nome', sa.String(length=500), nullable=False),
    sa.Column('grupo_nome', sa.String(length=500), nullable=False),
    sa.ForeignKeyConstraint(['ocorrencia_id'], ['contratos_diario_ocorrencias.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ocorrencia_id', 'item_id', name='contratos_diario_itens_avaliacao_ocorrencia_item_key')
    )
    op.create_index(op.f('ix_contratos_diario_itens_avaliacao_ocorrencia_id'), 'contratos_diario_itens_avaliacao', ['ocorrencia_id'], unique=False)
    op.add_column('contratos_competencias_avaliacoes', sa.Column('email_enviado_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column('contratos_competencias_avaliacoes', sa.Column('email_ok', sa.Boolean(), nullable=True))
    op.add_column('contratos_competencias_avaliacoes', sa.Column('email_destinatarios', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default=sa.text("'[]'"), nullable=False))
    op.add_column('contratos_competencias_avaliacoes', sa.Column('email_erro', sa.Text(), nullable=True))
    op.add_column('contratos_diario_ocorrencias', sa.Column('impacta_avaliacao', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('contratos_diario_ocorrencias', 'impacta_avaliacao')
    op.drop_column('contratos_competencias_avaliacoes', 'email_erro')
    op.drop_column('contratos_competencias_avaliacoes', 'email_destinatarios')
    op.drop_column('contratos_competencias_avaliacoes', 'email_ok')
    op.drop_column('contratos_competencias_avaliacoes', 'email_enviado_em')
    op.drop_index(op.f('ix_contratos_diario_itens_avaliacao_ocorrencia_id'), table_name='contratos_diario_itens_avaliacao')
    op.drop_table('contratos_diario_itens_avaliacao')
    op.drop_index(op.f('ix_contratos_diario_anexos_ocorrencia_id'), table_name='contratos_diario_anexos')
    op.drop_table('contratos_diario_anexos')
