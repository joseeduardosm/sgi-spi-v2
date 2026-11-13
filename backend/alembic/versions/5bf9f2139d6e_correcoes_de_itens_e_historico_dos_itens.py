"""
===============================================================================
ARQUIVO: 5bf9f2139d6e_correcoes_de_itens_e_historico_dos_itens.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Criar as tabelas de correção de itens do contrato, o histórico de mudanças dos
itens e a versão do cadastro sincronizada em cada competência.

RESUMO TÉCNICO:
- `contratos_correcoes_itens`: pedido de correção com justificativa, mudanças e
  prévia em JSON, situação (pendente, aplicada, recusada, cancelada) e quem
  decidiu.
- `contratos_itens_historico`: cada alteração aplicada em um item (campos
  antes/depois em JSON), com a versão do cadastro e a correção de origem.
- `contratos_competencias.versao_cadastro_sincronizada` (padrão 1).

FINALIDADE DE NEGÓCIO:
Corrigir um item cadastrado errado afeta medições e pagamentos; por isso a
correção passa por pedido e aprovação, fica registrada no histórico e cada
competência sabe com qual versão do cadastro foi calculada.

CONTEXTO NO SISTEMA:
Relaciona-se com `contratos`, `contratos_itens`, `contratos_competencias` e
`usuarios`. A versão do cadastro no contrato vem de `dd7999d97284`.

Revision ID: 5bf9f2139d6e
Revises: dd7999d97284
Create Date: 2026-10-02 22:28:46.017113

===============================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão (revision) e a anterior (down_revision)
revision: str = '5bf9f2139d6e'
down_revision: Union[str, Sequence[str], None] = 'dd7999d97284'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# upgrade() aplica esta mudança no banco (alembic upgrade) e downgrade() a
# desfaz (alembic downgrade), voltando à revisão anterior.
#
# As funções op.* do Alembic executam comandos de estrutura (DDL) no banco:
# create_table, add_column, alter_column, create_index, drop_* etc.
#
# op.f(nome) marca o nome do índice/restrição como definitivo, sem aplicar a
# convenção automática de nomes.
#
# server_default é o valor padrão gravado pelo próprio banco; serve também para
# preencher as linhas que já existiam quando a coluna é criada.
#
# sa.JSON().with_variant(JSONB, 'postgresql') usa o tipo JSONB (binário e
# indexável) no PostgreSQL e JSON comum nos demais bancos, como o SQLite dos
# testes.
def upgrade() -> None:
    """Cria as tabelas de correções e de histórico dos itens e a coluna de
    versão sincronizada nas competências.
    """
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.create_table('contratos_correcoes_itens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('contrato_id', sa.Uuid(), nullable=False),
    sa.Column('autor_id', sa.Integer(), nullable=True),
    sa.Column('autor_nome', sa.String(length=250), nullable=False),
    sa.Column('justificativa', sa.Text(), nullable=False),
    sa.Column('mudancas', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('previa', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('situacao', sa.String(length=12), nullable=False),
    sa.Column('decidido_por_id', sa.Integer(), nullable=True),
    sa.Column('decidido_por_nome', sa.String(length=250), nullable=False),
    sa.Column('decidido_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('motivo_decisao', sa.Text(), nullable=False),
    sa.Column('versao_cadastro', sa.Integer(), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("situacao IN ('pendente', 'aplicada', 'recusada', 'cancelada')", name='ck_contratos_correcoes_situacao'),
    sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['contrato_id'], ['contratos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['decidido_por_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contratos_correcoes_itens_contrato_id'), 'contratos_correcoes_itens', ['contrato_id'], unique=False)
    op.create_table('contratos_itens_historico',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('contrato_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.Uuid(), nullable=True),
    sa.Column('descricao_item', sa.String(length=1000), nullable=False),
    sa.Column('versao_cadastro', sa.Integer(), nullable=False),
    sa.Column('correcao_id', sa.Uuid(), nullable=True),
    sa.Column('autor_id', sa.Integer(), nullable=True),
    sa.Column('autor_nome', sa.String(length=250), nullable=False),
    sa.Column('motivo', sa.Text(), nullable=False),
    sa.Column('campos', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['contrato_id'], ['contratos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['correcao_id'], ['contratos_correcoes_itens.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['item_id'], ['contratos_itens.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contratos_itens_historico_contrato_id'), 'contratos_itens_historico', ['contrato_id'], unique=False)
    op.create_index(op.f('ix_contratos_itens_historico_item_id'), 'contratos_itens_historico', ['item_id'], unique=False)
    op.add_column('contratos_competencias', sa.Column('versao_cadastro_sincronizada', sa.Integer(), server_default='1', nullable=False))
    # Fim dos comandos gerados pelo autogenerate


def downgrade() -> None:
    """Remove a coluna e as tabelas; pedidos de correção e histórico se perdem.
    """
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.drop_column('contratos_competencias', 'versao_cadastro_sincronizada')
    op.drop_index(op.f('ix_contratos_itens_historico_item_id'), table_name='contratos_itens_historico')
    op.drop_index(op.f('ix_contratos_itens_historico_contrato_id'), table_name='contratos_itens_historico')
    op.drop_table('contratos_itens_historico')
    op.drop_index(op.f('ix_contratos_correcoes_itens_contrato_id'), table_name='contratos_correcoes_itens')
    op.drop_table('contratos_correcoes_itens')
    # Fim dos comandos gerados pelo autogenerate
