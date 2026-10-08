# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar os marcos (milestones) das equipes de tarefas e as atualizações de status da equipe.
"""tarefas: marcos e atualizações de status

Revision ID: e6f9a3b7c2d4
Revises: d5e8f2a6b1c3
Create Date: 2026-10-08 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f9a3b7c2d4"
down_revision: str | Sequence[str] | None = "d5e8f2a6b1c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Marcos, coluna da tarefa e atualizações de status."""
    op.create_table(
        "tarefas_marcos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("equipe_id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("data_alvo", sa.Date(), nullable=False),
        sa.Column("atingido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("atingido_manual", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("criado_por_id", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["equipe_id"], ["tarefas_equipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["criado_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipe_id", "nome", name="uq_tarefas_marcos_equipe_nome"),
    )
    op.create_index("ix_tarefas_marcos_equipe_id", "tarefas_marcos", ["equipe_id"])
    op.add_column("tarefas", sa.Column("marco_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_tarefas_marco", "tarefas", "tarefas_marcos", ["marco_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_tarefas_marco_id", "tarefas", ["marco_id"])
    op.create_table(
        "tarefas_atualizacoes_status",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("equipe_id", sa.Uuid(), nullable=False),
        sa.Column("situacao", sa.String(length=15), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("autor_id", sa.Integer(), nullable=True),
        sa.Column("autor_nome", sa.String(length=200), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("situacao IN ('no_prazo', 'em_risco', 'atrasado', 'em_espera', 'concluido')", name="ck_tarefas_atualizacoes_situacao"),
        sa.ForeignKeyConstraint(["equipe_id"], ["tarefas_equipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["autor_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tarefas_atualizacoes_equipe_em", "tarefas_atualizacoes_status", ["equipe_id", "criado_em"])


def downgrade() -> None:
    """Remove marcos e atualizações (as tarefas continuam, sem marco)."""
    op.drop_index("ix_tarefas_atualizacoes_equipe_em", table_name="tarefas_atualizacoes_status")
    op.drop_table("tarefas_atualizacoes_status")
    op.drop_index("ix_tarefas_marco_id", table_name="tarefas")
    op.drop_constraint("fk_tarefas_marco", "tarefas", type_="foreignkey")
    op.drop_column("tarefas", "marco_id")
    op.drop_index("ix_tarefas_marcos_equipe_id", table_name="tarefas_marcos")
    op.drop_table("tarefas_marcos")
