# Criado por José Eduardo Santana Martins
# Este arquivo serve para transformar os participantes das tarefas em responsáveis (renomeia a tabela e inclui o responsável principal).
"""tarefas: participantes viram responsáveis

Revision ID: e9f3a7c1b5d6
Revises: d8e2f6b0a4c5
Create Date: 2026-10-07 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9f3a7c1b5d6"
down_revision: str | Sequence[str] | None = "d8e2f6b0a4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Todos os participantes passam a ser responsáveis (mesma tabela, renomeada); o responsável principal de cada tarefa também entra na lista."""
    op.rename_table("tarefas_participantes", "tarefas_responsaveis")
    op.execute("ALTER TABLE tarefas_responsaveis RENAME CONSTRAINT uq_tarefas_participantes TO uq_tarefas_responsaveis")
    op.execute("ALTER INDEX IF EXISTS ix_tarefas_participantes_tarefa_id RENAME TO ix_tarefas_responsaveis_tarefa_id")
    op.execute("ALTER INDEX IF EXISTS ix_tarefas_participantes_usuario_id RENAME TO ix_tarefas_responsaveis_usuario_id")
    op.execute("ALTER SEQUENCE IF EXISTS tarefas_participantes_id_seq RENAME TO tarefas_responsaveis_id_seq")
    # Tarefas antigas (migradas) podem ter o responsável principal fora da lista de participantes
    op.execute(
        "INSERT INTO tarefas_responsaveis (tarefa_id, usuario_id) "
        "SELECT t.id, t.responsavel_id FROM tarefas t WHERE t.responsavel_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM tarefas_responsaveis r WHERE r.tarefa_id = t.id AND r.usuario_id = t.responsavel_id)"
    )


def downgrade() -> None:
    """Volta o nome antigo da tabela (os responsáveis incluídos continuam como participantes)."""
    op.execute("ALTER SEQUENCE IF EXISTS tarefas_responsaveis_id_seq RENAME TO tarefas_participantes_id_seq")
    op.execute("ALTER INDEX IF EXISTS ix_tarefas_responsaveis_usuario_id RENAME TO ix_tarefas_participantes_usuario_id")
    op.execute("ALTER INDEX IF EXISTS ix_tarefas_responsaveis_tarefa_id RENAME TO ix_tarefas_participantes_tarefa_id")
    op.execute("ALTER TABLE tarefas_responsaveis RENAME CONSTRAINT uq_tarefas_responsaveis TO uq_tarefas_participantes")
    op.rename_table("tarefas_responsaveis", "tarefas_participantes")
