# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as atividades agendadas das tarefas, os seguidores e o tipo de evento "atividade" da linha do tempo.
"""tarefas: atividades e seguidores

Revision ID: d5e8f2a6b1c3
Revises: c4d7e1f5a9b0
Create Date: 2026-10-08 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e8f2a6b1c3"
down_revision: str | Sequence[str] | None = "c4d7e1f5a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ANTIGOS = ("'criada', 'editada', 'status', 'entregue', 'validada', 'devolvida', 'reaberta', 'prazo', 'transferida', 'comentario', "
           "'participantes', 'marcadores', 'checklist', 'removido', 'escalonada'")


def upgrade() -> None:
    """Tabelas novas e o evento `atividade` na linha do tempo."""
    op.create_table(
        "tarefas_atividades",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tarefa_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("resumo", sa.String(length=200), nullable=False),
        sa.Column("nota", sa.Text(), nullable=False),
        sa.Column("prazo", sa.Date(), nullable=False),
        sa.Column("responsavel_id", sa.Integer(), nullable=True),
        sa.Column("criada_por_id", sa.Integer(), nullable=True),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluida_por_id", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.CheckConstraint("tipo IN ('fazer', 'ligar', 'email', 'reuniao', 'revisar', 'enviar_documento')", name="ck_tarefas_atividades_tipo"),
        sa.ForeignKeyConstraint(["tarefa_id"], ["tarefas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responsavel_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["criada_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["concluida_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tarefas_atividades_tarefa_id", "tarefas_atividades", ["tarefa_id"])
    op.create_index("ix_tarefas_atividades_responsavel_id", "tarefas_atividades", ["responsavel_id"])
    op.create_table(
        "tarefas_seguidores",
        sa.Column("tarefa_id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tarefa_id"], ["tarefas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tarefa_id", "usuario_id"),
    )
    op.create_index("ix_tarefas_seguidores_usuario_id", "tarefas_seguidores", ["usuario_id"])
    op.drop_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", type_="check")
    op.create_check_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", f"tipo IN ({ANTIGOS}, 'atividade')")


def downgrade() -> None:
    """Remove as tabelas (os eventos de atividade da linha do tempo são apagados)."""
    op.execute("DELETE FROM tarefas_eventos WHERE tipo = 'atividade'")
    op.drop_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", type_="check")
    op.create_check_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", f"tipo IN ({ANTIGOS})")
    op.drop_index("ix_tarefas_seguidores_usuario_id", table_name="tarefas_seguidores")
    op.drop_table("tarefas_seguidores")
    op.drop_index("ix_tarefas_atividades_responsavel_id", table_name="tarefas_atividades")
    op.drop_index("ix_tarefas_atividades_tarefa_id", table_name="tarefas_atividades")
    op.drop_table("tarefas_atividades")
