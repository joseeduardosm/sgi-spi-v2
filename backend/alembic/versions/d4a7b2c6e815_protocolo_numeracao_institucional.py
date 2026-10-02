# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas do Protocolo (numeração institucional por tipo de documento e exercício).
"""protocolo: tipos, sequências por exercício, números e linha do tempo

Revision ID: d4a7b2c6e815
Revises: c1f2a8d94e57
Create Date: 2026-10-02 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd4a7b2c6e815'
down_revision: Union[str, Sequence[str], None] = 'c1f2a8d94e57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'protocolo_tipos',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('nome', sa.String(length=200), nullable=False),
        sa.Column('nome_chave', sa.String(length=200), nullable=False),
        sa.Column('origem_sgi_id', sa.String(length=40), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nome_chave'),
        sa.UniqueConstraint('origem_sgi_id'),
    )
    op.create_table(
        'protocolo_sequencias',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tipo_id', sa.Uuid(), nullable=False),
        sa.Column('exercicio', sa.Integer(), nullable=False),
        sa.Column('inicio', sa.Integer(), nullable=False),
        sa.Column('fim', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tipo_id'], ['protocolo_tipos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tipo_id', 'exercicio', name='uq_protocolo_sequencias_tipo_exercicio'),
    )
    op.create_index('ix_protocolo_sequencias_tipo_id', 'protocolo_sequencias', ['tipo_id'])
    op.create_table(
        'protocolo_numeros',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('sequencia_id', sa.Uuid(), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('finalidade', sa.Text(), nullable=False),
        sa.Column('reservado_por_id', sa.Integer(), nullable=True),
        sa.Column('reservado_por_nome', sa.String(length=200), nullable=False),
        sa.Column('reservado_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('contrato_id', sa.Uuid(), nullable=True),
        sa.Column('anexo_id', sa.Uuid(), nullable=True),
        sa.Column('usado_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sigiloso', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('anulado_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('anulado_por_nome', sa.String(length=200), nullable=True),
        sa.Column('motivo_anulacao', sa.Text(), nullable=True),
        sa.Column('origem_sgi_id', sa.String(length=40), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['sequencia_id'], ['protocolo_sequencias.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reservado_por_id'], ['usuarios.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['contrato_id'], ['contratos.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['anexo_id'], ['anexos.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequencia_id', 'numero', name='uq_protocolo_numeros_sequencia_numero'),
        sa.UniqueConstraint('origem_sgi_id'),
    )
    op.create_index('ix_protocolo_numeros_sequencia_id', 'protocolo_numeros', ['sequencia_id'])
    op.create_index('ix_protocolo_numeros_contrato_id', 'protocolo_numeros', ['contrato_id'])
    op.create_index('ix_protocolo_numeros_reservado_por', 'protocolo_numeros', ['reservado_por_id', 'reservado_em'])
    op.create_table(
        'protocolo_eventos',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('numero_id', sa.Uuid(), nullable=False),
        sa.Column('tipo', sa.String(length=12), nullable=False),
        sa.Column('autor_id', sa.Integer(), nullable=True),
        sa.Column('autor_nome', sa.String(length=200), nullable=False),
        sa.Column('texto', sa.Text(), nullable=False),
        sa.Column('dados', _json(), nullable=True),
        sa.Column('ocorrido_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['numero_id'], ['protocolo_numeros.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_protocolo_eventos_numero_id', 'protocolo_eventos', ['numero_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_protocolo_eventos_numero_id', table_name='protocolo_eventos')
    op.drop_table('protocolo_eventos')
    op.drop_index('ix_protocolo_numeros_reservado_por', table_name='protocolo_numeros')
    op.drop_index('ix_protocolo_numeros_contrato_id', table_name='protocolo_numeros')
    op.drop_index('ix_protocolo_numeros_sequencia_id', table_name='protocolo_numeros')
    op.drop_table('protocolo_numeros')
    op.drop_index('ix_protocolo_sequencias_tipo_id', table_name='protocolo_sequencias')
    op.drop_table('protocolo_sequencias')
    op.drop_table('protocolo_tipos')
