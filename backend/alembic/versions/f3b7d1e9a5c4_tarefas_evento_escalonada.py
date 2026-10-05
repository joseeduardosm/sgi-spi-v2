# Criado por José Eduardo Santana Martins
# Este arquivo serve para aceitar o tipo de evento "escalonada" (aviso de atraso à liderança) na linha do tempo das tarefas.
"""tarefas: evento `escalonada` na linha do tempo

Revision ID: f3b7d1e9a5c4
Revises: e2a6c4d8b0f3
Create Date: 2026-10-05 18:00:00
"""

from collections.abc import Sequence

from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f3b7d1e9a5c4"
down_revision: str | Sequence[str] | None = "e2a6c4d8b0f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
