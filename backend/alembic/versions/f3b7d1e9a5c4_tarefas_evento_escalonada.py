"""
===============================================================================
ARQUIVO: f3b7d1e9a5c4_tarefas_evento_escalonada.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que aceita o tipo de evento escalonada na linha do tempo das
tarefas (aviso de atraso enviado à liderança).

RESUMO TÉCNICO:
Recria a check constraint ck_tarefas_eventos_tipo com a lista ANTIGOS mais
'escalonada'. O downgrade apaga antes os eventos escalonada, que a restrição
antiga não aceita, e volta a lista anterior.

FINALIDADE DE NEGÓCIO:
Quando uma tarefa atrasa, a chefia é avisada (escalonamento) e esse aviso fica
registrado no histórico da tarefa para todos verem.

CONTEXTO NO SISTEMA:
Tabela tarefas_eventos; serviço app/services/tarefas/servico_tarefas.py.
Aplicada com 'alembic upgrade head' (o instalador e a atualização do sistema
rodam esse comando).

Revision ID: f3b7d1e9a5c4
Revises: e2a6c4d8b0f3
Create Date: 2026-10-05 18:00:00

===============================================================================
"""

from collections.abc import Sequence

from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f3b7d1e9a5c4"
down_revision: str | Sequence[str] | None = "e2a6c4d8b0f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tipos de evento que a check constraint aceitava antes desta migração
ANTIGOS = "'criada', 'editada', 'status', 'entregue', 'validada', 'devolvida', 'reaberta', 'prazo', 'transferida', 'comentario', 'participantes', 'marcadores', 'checklist', 'removido'"


def upgrade() -> None:
    """Recria a restrição de tipos incluindo `escalonada`."""
    op.drop_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", type_="check")
    op.create_check_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", f"tipo IN ({ANTIGOS}, 'escalonada')")


def downgrade() -> None:
    """Volta à restrição anterior (apaga antes os eventos `escalonada`, que ela não aceita)."""
    op.execute("DELETE FROM tarefas_eventos WHERE tipo = 'escalonada'")
    op.drop_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", type_="check")
    op.create_check_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", f"tipo IN ({ANTIGOS})")
