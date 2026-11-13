"""
===============================================================================
ARQUIVO: 57c0f7e1349f_diario_anexos_impacto_na_avaliacao_e_.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Acrescentar anexos e impacto na avaliação às ocorrências do diário de bordo e
registrar o resultado do e-mail da avaliação enviado à contratada.

RESUMO TÉCNICO:
- `contratos_diario_anexos`: arquivos de cada ocorrência (RESTRICT no anexo).
- `contratos_diario_itens_avaliacao`: itens do formulário de avaliação que a
  ocorrência afeta (cópia do nome do item e do grupo; um por ocorrência).
- `contratos_diario_ocorrencias.impacta_avaliacao` (padrão falso).
- `contratos_competencias_avaliacoes`: data, sucesso, destinatários e erro do
  e-mail enviado à contratada.

FINALIDADE DE NEGÓCIO:
O diário de bordo é o registro das ocorrências do contrato pela fiscalização.
Ligar a ocorrência aos itens da avaliação dá base documental para a nota da
empresa no mês, e o registro do e-mail comprova a ciência.

CONTEXTO NO SISTEMA:
Tabelas do diário (`contratos_diario_ocorrencias`, criada em `7566f71dd5a5`) e
da avaliação por competência; serviço
`app/services/contratos/servico_diario.py`.

Revision ID: 57c0f7e1349f
Revises: aef1af3a69ff
Create Date: 2026-09-30 21:07:18.519506

===============================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão (revision) e a anterior (down_revision)
revision: str = '57c0f7e1349f'
down_revision: Union[str, Sequence[str], None] = 'aef1af3a69ff'
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
    """Cria as tabelas de anexos e de itens de avaliação do diário e as colunas
    novas da ocorrência e da avaliação.
    """
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
    """Remove as colunas e as tabelas criadas; anexos vinculados e itens
    impactados se perdem.
    """
    op.drop_column('contratos_diario_ocorrencias', 'impacta_avaliacao')
    op.drop_column('contratos_competencias_avaliacoes', 'email_erro')
    op.drop_column('contratos_competencias_avaliacoes', 'email_destinatarios')
    op.drop_column('contratos_competencias_avaliacoes', 'email_ok')
    op.drop_column('contratos_competencias_avaliacoes', 'email_enviado_em')
    op.drop_index(op.f('ix_contratos_diario_itens_avaliacao_ocorrencia_id'), table_name='contratos_diario_itens_avaliacao')
    op.drop_table('contratos_diario_itens_avaliacao')
    op.drop_index(op.f('ix_contratos_diario_anexos_ocorrencia_id'), table_name='contratos_diario_anexos')
    op.drop_table('contratos_diario_anexos')
