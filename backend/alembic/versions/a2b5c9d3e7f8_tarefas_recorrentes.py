# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas das tarefas recorrentes e ligar cada tarefa gerada à sua série.
"""tarefas: recorrência

Revision ID: a2b5c9d3e7f8
Revises: f1a4b8d2c6e7
Create Date: 2026-10-08 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2b5c9d3e7f8"
down_revision: str | Sequence[str] | None = "f1a4b8d2c6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Séries recorrentes, responsáveis e marcadores do modelo, e as colunas da tarefa que apontam para a série."""
    op.create_table(
        "tarefas_recorrencias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("equipe_id", sa.Uuid(), nullable=True),
        sa.Column("criado_por_id", sa.Integer(), nullable=True),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("prioridade", sa.String(length=10), nullable=False),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("frequencia", sa.String(length=10), nullable=False),
        sa.Column("intervalo", sa.Integer(), nullable=False),
        sa.Column("dias_semana", sa.JSON(), nullable=False),
        sa.Column("somente_dias_uteis", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("antecedencia_dias", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hora_prazo", sa.Time(), nullable=False),
        sa.Column("inicio", sa.Date(), nullable=False),
        sa.Column("fim", sa.Date(), nullable=True),
        sa.Column("max_ocorrencias", sa.Integer(), nullable=True),
        sa.Column("ativa", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("proxima_data", sa.Date(), nullable=True),
        sa.Column("geradas", sa.Integer(), nullable=False),
        sa.Column("ultimo_erro", sa.Text(), server_default="", nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("frequencia IN ('diaria', 'semanal', 'mensal', 'anual')", name="ck_tarefas_recorrencias_frequencia"),
        sa.CheckConstraint("intervalo >= 1", name="ck_tarefas_recorrencias_intervalo"),
        sa.ForeignKeyConstraint(["equipe_id"], ["tarefas_equipes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["criado_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tarefas_recorrencias_equipe_id", "tarefas_recorrencias", ["equipe_id"])
    op.create_table(
        "tarefas_recorrencias_responsaveis",
        sa.Column("recorrencia_id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("posicao", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["recorrencia_id"], ["tarefas_recorrencias.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("recorrencia_id", "usuario_id"),
    )
    op.create_table(
        "tarefas_recorrencias_marcadores",
        sa.Column("recorrencia_id", sa.Uuid(), nullable=False),
        sa.Column("marcador_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["recorrencia_id"], ["tarefas_recorrencias.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["marcador_id"], ["tarefas_marcadores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("recorrencia_id", "marcador_id"),
    )
    op.add_column("tarefas", sa.Column("recorrencia_id", sa.Uuid(), nullable=True))
    op.add_column("tarefas", sa.Column("ocorrencia_em", sa.Date(), nullable=True))
    op.create_foreign_key("fk_tarefas_recorrencia", "tarefas", "tarefas_recorrencias", ["recorrencia_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_tarefas_recorrencia_id", "tarefas", ["recorrencia_id"])
    op.create_unique_constraint("uq_tarefas_recorrencia_ocorrencia", "tarefas", ["recorrencia_id", "ocorrencia_em"])


def downgrade() -> None:
    """Remove as séries (as tarefas já geradas continuam, como tarefas comuns)."""
    op.drop_constraint("uq_tarefas_recorrencia_ocorrencia", "tarefas", type_="unique")
    op.drop_index("ix_tarefas_recorrencia_id", table_name="tarefas")
    op.drop_constraint("fk_tarefas_recorrencia", "tarefas", type_="foreignkey")
    op.drop_column("tarefas", "ocorrencia_em")
    op.drop_column("tarefas", "recorrencia_id")
    op.drop_table("tarefas_recorrencias_marcadores")
    op.drop_table("tarefas_recorrencias_responsaveis")
    op.drop_index("ix_tarefas_recorrencias_equipe_id", table_name="tarefas_recorrencias")
    op.drop_table("tarefas_recorrencias")
