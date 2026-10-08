# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as subtarefas (tarefa mãe) e as dependências entre tarefas.
"""tarefas: subtarefas e dependências

Revision ID: b3c6d0e4f8a9
Revises: a2b5c9d3e7f8
Create Date: 2026-10-08 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c6d0e4f8a9"
down_revision: str | Sequence[str] | None = "a2b5c9d3e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Coluna da tarefa mãe e tabela de dependências."""
    op.add_column("tarefas", sa.Column("tarefa_pai_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_tarefas_tarefa_pai", "tarefas", "tarefas", ["tarefa_pai_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_tarefas_tarefa_pai_id", "tarefas", ["tarefa_pai_id"])
    op.create_table(
        "tarefas_dependencias",
        sa.Column("tarefa_id", sa.Uuid(), nullable=False),
        sa.Column("bloqueada_por_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("tarefa_id <> bloqueada_por_id", name="ck_tarefas_dependencias_propria"),
        sa.ForeignKeyConstraint(["tarefa_id"], ["tarefas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bloqueada_por_id"], ["tarefas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tarefa_id", "bloqueada_por_id"),
    )
    op.create_index("ix_tarefas_dependencias_bloqueada_por_id", "tarefas_dependencias", ["bloqueada_por_id"])


def downgrade() -> None:
    """Remove as dependências e o vínculo com a tarefa mãe (as subtarefas viram tarefas comuns)."""
    op.drop_index("ix_tarefas_dependencias_bloqueada_por_id", table_name="tarefas_dependencias")
    op.drop_table("tarefas_dependencias")
    op.drop_index("ix_tarefas_tarefa_pai_id", table_name="tarefas")
    op.drop_constraint("fk_tarefas_tarefa_pai", "tarefas", type_="foreignkey")
    op.drop_column("tarefas", "tarefa_pai_id")
