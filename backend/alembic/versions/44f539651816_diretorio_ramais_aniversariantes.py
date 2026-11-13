"""
===============================================================================
ARQUIVO: 44f539651816_diretorio_ramais_aniversariantes.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Criar os favoritos do diretório de ramais, o mural de parabéns dos
aniversariantes e as colunas de foto e de ocultar aniversário no usuário.

RESUMO TÉCNICO:
- `diretorio_favoritos`: par (usuário, favorito), chave primária composta.
- `diretorio_parabens`: mensagem de um autor a um aniversariante; no máximo uma
  por autor, aniversariante e ano (restrição única).
- `usuarios`: `foto_anexo_id` (FK para `anexos`, SET NULL), `foto_origem` e
  `ocultar_aniversario` (padrão falso).

FINALIDADE DE NEGÓCIO:
Aproxima as equipes da SPI: o diretório mostra ramais e fotos, permite marcar
colegas favoritos e deixar parabéns no aniversário; quem não quer divulgar a
data pode ocultá-la.

CONTEXTO NO SISTEMA:
Relaciona-se com `usuarios` e `anexos`; usado pelo módulo Diretório (rotas e
tela de ramais/aniversariantes). Curtidas vêm depois em `c3e7a1f5b9d2`.

Revision ID: 44f539651816
Revises: 5bf9f2139d6e
Create Date: 2026-10-03 22:14:18.241522

===============================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Identificação da migração: esta revisão (revision) e a anterior (down_revision)
revision: str = '44f539651816'
down_revision: Union[str, Sequence[str], None] = '5bf9f2139d6e'
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
def upgrade() -> None:
    """Cria as tabelas de favoritos e de parabéns e as colunas novas em
    `usuarios`, com a chave estrangeira da foto.
    """
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.create_table('diretorio_favoritos',
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('favorito_id', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['favorito_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('usuario_id', 'favorito_id')
    )
    op.create_table('diretorio_parabens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('aniversariante_id', sa.Integer(), nullable=False),
    sa.Column('autor_id', sa.Integer(), nullable=False),
    sa.Column('autor_nome', sa.String(length=200), nullable=False),
    sa.Column('ano', sa.Integer(), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['aniversariante_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('aniversariante_id', 'autor_id', 'ano', name='uq_diretorio_parabens_autor_ano')
    )
    op.create_index(op.f('ix_diretorio_parabens_aniversariante_id'), 'diretorio_parabens', ['aniversariante_id'], unique=False)
    op.add_column('usuarios', sa.Column('foto_anexo_id', sa.Uuid(), nullable=True))
    op.add_column('usuarios', sa.Column('foto_origem', sa.String(length=10), nullable=True))
    op.add_column('usuarios', sa.Column('ocultar_aniversario', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.create_foreign_key('fk_usuarios_foto_anexo_id', 'usuarios', 'anexos', ['foto_anexo_id'], ['id'], ondelete='SET NULL')
    # Fim dos comandos gerados pelo autogenerate


def downgrade() -> None:
    """Remove a chave estrangeira, as colunas de `usuarios` e as tabelas.
    Favoritos e mensagens de parabéns se perdem.
    """
    # Comandos gerados pelo autogenerate do Alembic (revisados à mão)
    op.drop_constraint('fk_usuarios_foto_anexo_id', 'usuarios', type_='foreignkey')
    op.drop_column('usuarios', 'ocultar_aniversario')
    op.drop_column('usuarios', 'foto_origem')
    op.drop_column('usuarios', 'foto_anexo_id')
    op.drop_index(op.f('ix_diretorio_parabens_aniversariante_id'), table_name='diretorio_parabens')
    op.drop_table('diretorio_parabens')
    op.drop_table('diretorio_favoritos')
    # Fim dos comandos gerados pelo autogenerate
