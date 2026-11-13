"""
===============================================================================
ARQUIVO: 2320f1538b36_tarefas_modulo.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Criar as tabelas do Módulo Tarefas: equipes, tarefas, participantes, linha do
tempo (eventos e seus anexos), marcadores e checklist.

RESUMO TÉCNICO:
- `tarefas_equipes` (+ `_membros`, `_lideres`): equipes próprias do módulo, com
  dono, líderes e equipe pai (hierarquia).
- `tarefas`: fluxo a_fazer, em_andamento, em_validacao, concluida; prazo e
  prazo original, datas de cada etapa, tempo acumulado em andamento e `versao`
  (controle de edição concorrente). Número sequencial único.
- `tarefas_participantes`, `tarefas_eventos` (+ `_anexos`),
  `tarefas_marcadores` (+ `_vinculos`) e `tarefas_checklist`.
- Restrições CHECK limitam prioridade, status e tipos de evento.

FINALIDADE DE NEGÓCIO:
Organiza o trabalho das equipes da SPI em quadros de tarefas com prazos,
responsável, validação por líder e histórico completo, dando visibilidade do
que está atrasado e de quem está com cada demanda.

CONTEXTO NO SISTEMA:
Relaciona-se com `usuarios` e `anexos`. Usado pelos modelos em
`app/models/tarefas.py`, pelo serviço `app/services/tarefas/` e pelas rotas
`app/api/routes/tarefas.py`. Migrações seguintes acrescentam subtarefas,
recorrência, estágios, RDM etc.

Revision ID: 2320f1538b36
Revises: b2e4f6a8c0d1
Create Date: 2026-09-30 10:00:00

===============================================================================
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Identificação da migração: esta revisão e a anterior
revision: str = '2320f1538b36'
down_revision: Union[str, Sequence[str], None] = 'b2e4f6a8c0d1'
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
def upgrade() -> None:
    """Cria as tabelas do módulo Tarefas, na ordem das dependências (equipes
    antes de tarefas, tarefas antes de eventos), com índices e restrições.
    """
    op.create_table('tarefas_equipes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('nome', sa.String(length=150), nullable=False),
    sa.Column('dono_id', sa.Integer(), nullable=True),
    sa.Column('equipe_pai_id', sa.Uuid(), nullable=True),
    sa.Column('ativa', sa.Boolean(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['dono_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['equipe_pai_id'], ['tarefas_equipes.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tarefas',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('numero', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=False),
    sa.Column('equipe_id', sa.Uuid(), nullable=True),
    sa.Column('criado_por_id', sa.Integer(), nullable=True),
    sa.Column('responsavel_id', sa.Integer(), nullable=True),
    sa.Column('prazo', sa.DateTime(timezone=True), nullable=False),
    sa.Column('prazo_original', sa.DateTime(timezone=True), nullable=False),
    sa.Column('prioridade', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=15), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.Column('iniciada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('em_andamento_desde', sa.DateTime(timezone=True), nullable=True),
    sa.Column('segundos_em_andamento', sa.BigInteger(), nullable=False),
    sa.Column('entregue_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('concluida_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('versao', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("prioridade IN ('baixa', 'normal', 'alta', 'critica')", name='ck_tarefas_prioridade'),
    sa.CheckConstraint("status IN ('a_fazer', 'em_andamento', 'em_validacao', 'concluida')", name='ck_tarefas_status'),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['equipe_id'], ['tarefas_equipes.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['responsavel_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('numero')
    )
    op.create_index(op.f('ix_tarefas_equipe_id'), 'tarefas', ['equipe_id'], unique=False)
    # Índices compostos para os quadros: tarefas de uma equipe por status e
    # tarefas de um responsável por status.
    op.create_index('ix_tarefas_equipe_status', 'tarefas', ['equipe_id', 'status'], unique=False)
    op.create_index('ix_tarefas_responsavel_status', 'tarefas', ['responsavel_id', 'status'], unique=False)
    op.create_table('tarefas_equipes_lideres',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('equipe_id', sa.Uuid(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['equipe_id'], ['tarefas_equipes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('equipe_id', 'usuario_id', name='uq_tarefas_equipes_lideres')
    )
    op.create_index(op.f('ix_tarefas_equipes_lideres_equipe_id'), 'tarefas_equipes_lideres', ['equipe_id'], unique=False)
    op.create_index(op.f('ix_tarefas_equipes_lideres_usuario_id'), 'tarefas_equipes_lideres', ['usuario_id'], unique=False)
    op.create_table('tarefas_equipes_membros',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('equipe_id', sa.Uuid(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['equipe_id'], ['tarefas_equipes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('equipe_id', 'usuario_id', name='uq_tarefas_equipes_membros')
    )
    op.create_index(op.f('ix_tarefas_equipes_membros_equipe_id'), 'tarefas_equipes_membros', ['equipe_id'], unique=False)
    op.create_index(op.f('ix_tarefas_equipes_membros_usuario_id'), 'tarefas_equipes_membros', ['usuario_id'], unique=False)
    op.create_table('tarefas_marcadores',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('equipe_id', sa.Uuid(), nullable=True),
    sa.Column('nome', sa.String(length=60), nullable=False),
    sa.Column('cor', sa.String(length=7), nullable=False),
    sa.ForeignKeyConstraint(['equipe_id'], ['tarefas_equipes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('equipe_id', 'nome', name='uq_tarefas_marcadores_equipe_nome')
    )
    op.create_index(op.f('ix_tarefas_marcadores_equipe_id'), 'tarefas_marcadores', ['equipe_id'], unique=False)
    op.create_table('tarefas_checklist',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('tarefa_id', sa.Uuid(), nullable=False),
    sa.Column('texto', sa.String(length=300), nullable=False),
    sa.Column('posicao', sa.Integer(), nullable=False),
    sa.Column('concluido_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tarefas_checklist_tarefa_id'), 'tarefas_checklist', ['tarefa_id'], unique=False)
    op.create_table('tarefas_eventos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('tarefa_id', sa.Uuid(), nullable=False),
    sa.Column('tipo', sa.String(length=15), nullable=False),
    sa.Column('autor_id', sa.Integer(), nullable=True),
    sa.Column('autor_nome', sa.String(length=200), nullable=False),
    sa.Column('titulo', sa.String(length=300), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('dados', sa.JSON(), nullable=False),
    sa.Column('removido_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('removido_por_nome', sa.String(length=200), nullable=True),
    sa.Column('motivo_remocao', sa.Text(), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("tipo IN ('criada', 'editada', 'status', 'entregue', 'validada', 'devolvida', 'reaberta', 'prazo', 'transferida', 'comentario', 'participantes', 'marcadores', 'checklist', 'removido')", name='ck_tarefas_eventos_tipo'),
    sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tarefas_eventos_tarefa_em', 'tarefas_eventos', ['tarefa_id', 'criado_em'], unique=False)
    # Tabela de ligação muitos-para-muitos entre tarefas e marcadores; a chave
    # primária é o próprio par (tarefa, marcador).
    op.create_table('tarefas_marcadores_vinculos',
    sa.Column('tarefa_id', sa.Uuid(), nullable=False),
    sa.Column('marcador_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['marcador_id'], ['tarefas_marcadores.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tarefa_id', 'marcador_id')
    )
    op.create_table('tarefas_participantes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tarefa_id', sa.Uuid(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefas.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tarefa_id', 'usuario_id', name='uq_tarefas_participantes')
    )
    op.create_index(op.f('ix_tarefas_participantes_tarefa_id'), 'tarefas_participantes', ['tarefa_id'], unique=False)
    op.create_index(op.f('ix_tarefas_participantes_usuario_id'), 'tarefas_participantes', ['usuario_id'], unique=False)
    op.create_table('tarefas_eventos_anexos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('evento_id', sa.Uuid(), nullable=False),
    sa.Column('anexo_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['anexo_id'], ['anexos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['evento_id'], ['tarefas_eventos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tarefas_eventos_anexos_evento_id'), 'tarefas_eventos_anexos', ['evento_id'], unique=False)


def downgrade() -> None:
    """Remove as tabelas do módulo na ordem inversa (dependentes primeiro). Os
    dados se perdem.
    """
    op.drop_index(op.f('ix_tarefas_eventos_anexos_evento_id'), table_name='tarefas_eventos_anexos')
    op.drop_table('tarefas_eventos_anexos')
    op.drop_index(op.f('ix_tarefas_participantes_usuario_id'), table_name='tarefas_participantes')
    op.drop_index(op.f('ix_tarefas_participantes_tarefa_id'), table_name='tarefas_participantes')
    op.drop_table('tarefas_participantes')
    op.drop_table('tarefas_marcadores_vinculos')
    op.drop_index('ix_tarefas_eventos_tarefa_em', table_name='tarefas_eventos')
    op.drop_table('tarefas_eventos')
    op.drop_index(op.f('ix_tarefas_checklist_tarefa_id'), table_name='tarefas_checklist')
    op.drop_table('tarefas_checklist')
    op.drop_index(op.f('ix_tarefas_marcadores_equipe_id'), table_name='tarefas_marcadores')
    op.drop_table('tarefas_marcadores')
    op.drop_index(op.f('ix_tarefas_equipes_membros_usuario_id'), table_name='tarefas_equipes_membros')
    op.drop_index(op.f('ix_tarefas_equipes_membros_equipe_id'), table_name='tarefas_equipes_membros')
    op.drop_table('tarefas_equipes_membros')
    op.drop_index(op.f('ix_tarefas_equipes_lideres_usuario_id'), table_name='tarefas_equipes_lideres')
    op.drop_index(op.f('ix_tarefas_equipes_lideres_equipe_id'), table_name='tarefas_equipes_lideres')
    op.drop_table('tarefas_equipes_lideres')
    op.drop_index('ix_tarefas_responsavel_status', table_name='tarefas')
    op.drop_index('ix_tarefas_equipe_status', table_name='tarefas')
    op.drop_index(op.f('ix_tarefas_equipe_id'), table_name='tarefas')
    op.drop_table('tarefas')
    op.drop_table('tarefas_equipes')
