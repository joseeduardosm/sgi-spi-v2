"""
===============================================================================
ARQUIVO: 554e409aefd2_preferencias_de_colunas_das_listagens.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Criar a tabela que guarda quais colunas cada usuário escolheu mostrar em cada
listagem do sistema.

RESUMO TÉCNICO:
Cria `usuarios_preferencias_colunas`: usuário, identificador da tela e a lista
de colunas em JSON; uma linha por usuário e tela (restrição única) e CASCADE ao
apagar o usuário.

FINALIDADE DE NEGÓCIO:
Cada servidor monta a tabela do jeito que trabalha (mostrando só as colunas
úteis) e encontra a mesma escolha ao voltar, em qualquer computador.

CONTEXTO NO SISTEMA:
Relaciona-se com `usuarios`; usada pelas rotas de preferências e pelo seletor
de colunas das listagens do Angular. A visão global vem em `c3badbe90657`.

Revision ID: 554e409aefd2
Revises: b7d2e9a4c1f3
Create Date: 2026-10-12 01:59:32.989355

===============================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão (revision) e a anterior (down_revision)
revision: str = '554e409aefd2'
down_revision: Union[str, Sequence[str], None] = 'b7d2e9a4c1f3'
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
# sa.JSON().with_variant(JSONB, 'postgresql') usa o tipo JSONB (binário e
# indexável) no PostgreSQL e JSON comum nos demais bancos, como o SQLite dos
# testes.
def upgrade() -> None:
    """Cria a tabela de preferências de colunas e o índice por usuário."""
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.create_table('usuarios_preferencias_colunas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tela', sa.String(length=60), nullable=False),
    sa.Column('colunas', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'tela', name='uq_usuarios_preferencias_colunas_tela')
    )
    op.create_index(op.f('ix_usuarios_preferencias_colunas_usuario_id'), 'usuarios_preferencias_colunas', ['usuario_id'], unique=False)
    # Fim dos comandos gerados pelo autogenerate


def downgrade() -> None:
    """Remove o índice e a tabela; as escolhas de colunas se perdem."""
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.drop_index(op.f('ix_usuarios_preferencias_colunas_usuario_id'), table_name='usuarios_preferencias_colunas')
    op.drop_table('usuarios_preferencias_colunas')
    # Fim dos comandos gerados pelo autogenerate
