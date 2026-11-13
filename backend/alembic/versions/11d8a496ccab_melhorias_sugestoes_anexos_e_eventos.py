"""
===============================================================================
ARQUIVO: 11d8a496ccab_melhorias_sugestoes_anexos_e_eventos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Criar as tabelas do Módulo Melhorias (sugestões dos usuários, prints anexados e
histórico da triagem) e cadastrar o recurso `melhorias` na ACL.

RESUMO TÉCNICO:
- `melhorias_sugestoes`: texto, tela e módulo de onde veio, situação (nova,
  em_analise, aceita, recusada, concluida), resposta pública, observação
  interna e tarefa vinculada; número sequencial único.
- `melhorias_anexos`: liga a sugestão aos arquivos de `anexos` (RESTRICT impede
  apagar um anexo ainda usado).
- `melhorias_eventos`: cada mudança de situação, com autor e data.
- Recurso de ACL `melhorias` inserido só se ainda não existir; nasce sem
  regras, então só o SuperRoot faz a triagem até alguém receber CONTROLE_TOTAL.

FINALIDADE DE NEGÓCIO:
Permite que qualquer servidor da SPI sugira melhorias no sistema a partir da
tela em que está, e que a equipe responsável faça a triagem e devolva uma
resposta, com histórico transparente.

CONTEXTO NO SISTEMA:
Relaciona-se com `usuarios`, `anexos`, `tarefas` (sugestão aceita pode virar
tarefa) e `acl_recursos`. Usado pelo módulo Melhorias do backend e pela tela de
sugestões no Angular.

Revision ID: 11d8a496ccab
Revises: b3d91e7a0c24
Create Date: 2026-09-30 21:54:44.616414

===============================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Identificação da migração: esta revisão (revision) e a anterior (down_revision)
revision: str = '11d8a496ccab'
down_revision: Union[str, Sequence[str], None] = 'b3d91e7a0c24'
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
# op.execute() roda um comando SQL escrito à mão, em geral para ajustar ou
# semear dados.
def upgrade() -> None:
    """Cria as três tabelas do módulo com seus índices e insere o recurso
    `melhorias` na ACL (o INSERT ... WHERE NOT EXISTS evita duplicar).
    """
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.create_table('melhorias_sugestoes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('numero', sa.Integer(), nullable=False),
    sa.Column('autor_id', sa.Integer(), nullable=True),
    sa.Column('autor_nome', sa.String(length=250), nullable=False),
    sa.Column('autor_login', sa.String(length=150), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('tela', sa.String(length=1000), nullable=False),
    sa.Column('modulo', sa.String(length=40), nullable=False),
    sa.Column('situacao', sa.String(length=20), nullable=False),
    sa.Column('resposta_publica', sa.Text(), nullable=False),
    sa.Column('observacao_interna', sa.Text(), nullable=False),
    sa.Column('tarefa_id', sa.Uuid(), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('atualizado_por_id', sa.Integer(), nullable=True),
    sa.Column('atualizado_por_nome', sa.String(length=250), nullable=False),
    sa.CheckConstraint("situacao IN ('nova', 'em_analise', 'aceita', 'recusada', 'concluida')", name='ck_melhorias_sugestoes_situacao'),
    sa.ForeignKeyConstraint(['atualizado_por_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefas.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('numero')
    )
    op.create_index(op.f('ix_melhorias_sugestoes_autor_id'), 'melhorias_sugestoes', ['autor_id'], unique=False)
    op.create_index(op.f('ix_melhorias_sugestoes_criado_em'), 'melhorias_sugestoes', ['criado_em'], unique=False)
    op.create_index(op.f('ix_melhorias_sugestoes_modulo'), 'melhorias_sugestoes', ['modulo'], unique=False)
    op.create_index(op.f('ix_melhorias_sugestoes_situacao'), 'melhorias_sugestoes', ['situacao'], unique=False)
    op.create_table('melhorias_anexos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sugestao_id', sa.Uuid(), nullable=False),
    sa.Column('anexo_id', sa.Uuid(), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['anexo_id'], ['anexos.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['sugestao_id'], ['melhorias_sugestoes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_melhorias_anexos_sugestao_id'), 'melhorias_anexos', ['sugestao_id'], unique=False)
    op.create_table('melhorias_eventos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sugestao_id', sa.Uuid(), nullable=False),
    sa.Column('descricao', sa.String(length=500), nullable=False),
    sa.Column('situacao_anterior', sa.String(length=20), nullable=False),
    sa.Column('situacao_nova', sa.String(length=20), nullable=False),
    sa.Column('autor_id', sa.Integer(), nullable=True),
    sa.Column('autor_nome', sa.String(length=250), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['sugestao_id'], ['melhorias_sugestoes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_melhorias_eventos_sugestao_id'), 'melhorias_eventos', ['sugestao_id'], unique=False)
    # Fim dos comandos gerados pelo autogenerate
    # Semeia o recurso na ACL sem regras: ninguém além do SuperRoot
    # (administrador com a coluna `superusuario`) tem acesso de triagem até ser
    # configurado.
    op.execute("INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
               "SELECT 'Melhorias', 'melhorias', 'Sugestões de melhoria: todos enviam; CONTROLE_TOTAL faz a triagem.', "
               "'/melhorias', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
               "WHERE NOT EXISTS (SELECT 1 FROM acl_recursos WHERE slug = 'melhorias')")


def downgrade() -> None:
    """Remove o recurso da ACL e as tabelas, das dependentes (eventos, anexos)
    para a principal (sugestões). Os dados se perdem.
    """
    op.execute("DELETE FROM acl_recursos WHERE slug = 'melhorias'")
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.drop_index(op.f('ix_melhorias_eventos_sugestao_id'), table_name='melhorias_eventos')
    op.drop_table('melhorias_eventos')
    op.drop_index(op.f('ix_melhorias_anexos_sugestao_id'), table_name='melhorias_anexos')
    op.drop_table('melhorias_anexos')
    op.drop_index(op.f('ix_melhorias_sugestoes_situacao'), table_name='melhorias_sugestoes')
    op.drop_index(op.f('ix_melhorias_sugestoes_modulo'), table_name='melhorias_sugestoes')
    op.drop_index(op.f('ix_melhorias_sugestoes_criado_em'), table_name='melhorias_sugestoes')
    op.drop_index(op.f('ix_melhorias_sugestoes_autor_id'), table_name='melhorias_sugestoes')
    op.drop_table('melhorias_sugestoes')
    # Fim dos comandos gerados pelo autogenerate
