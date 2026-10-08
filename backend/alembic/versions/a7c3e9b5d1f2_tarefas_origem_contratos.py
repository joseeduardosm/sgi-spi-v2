# Criado por José Eduardo Santana Martins
# Este arquivo serve para ligar tarefas a outro módulo (origem) e aceitar o evento "contrato" na linha do tempo, para as tarefas das competências de contratos.
"""tarefas: origem em outro módulo, controle externo e evento `contrato`

Revision ID: a7c3e9b5d1f2
Revises: e6f9a3b7c2d4
Create Date: 2026-10-08 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a7c3e9b5d1f2"
down_revision: str | Sequence[str] | None = "e6f9a3b7c2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ANTIGOS = (
    "'criada', 'editada', 'status', 'entregue', 'validada', 'devolvida', 'reaberta', 'prazo', 'transferida', 'comentario', 'participantes', "
    "'marcadores', 'checklist', 'removido', 'escalonada', 'atividade'"
)


def upgrade() -> None:
    """Colunas de origem na tarefa, unicidade por origem e o tipo de evento `contrato`."""
    op.add_column("tarefas", sa.Column("origem_tipo", sa.String(length=30), nullable=True))
    op.add_column("tarefas", sa.Column("origem_id", sa.Uuid(), nullable=True))
    op.add_column("tarefas", sa.Column("origem_chave", sa.String(length=80), nullable=True))
    op.add_column("tarefas", sa.Column("controlada_externamente", sa.Boolean(), server_default="false", nullable=False))
    op.create_index("ix_tarefas_origem_id", "tarefas", ["origem_id"])
    op.create_unique_constraint("uq_tarefas_origem", "tarefas", ["origem_tipo", "origem_id", "origem_chave"])
    op.drop_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", type_="check")
    op.create_check_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", f"tipo IN ({ANTIGOS}, 'contrato')")


def downgrade() -> None:
    """Desfaz: apaga os eventos `contrato` (a restrição antiga não os aceita) e as colunas de origem."""
    op.execute("DELETE FROM tarefas_eventos WHERE tipo = 'contrato'")
    op.drop_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", type_="check")
    op.create_check_constraint("ck_tarefas_eventos_tipo", "tarefas_eventos", f"tipo IN ({ANTIGOS})")
    op.drop_constraint("uq_tarefas_origem", "tarefas", type_="unique")
    op.drop_index("ix_tarefas_origem_id", table_name="tarefas")
    op.drop_column("tarefas", "controlada_externamente")
    op.drop_column("tarefas", "origem_chave")
    op.drop_column("tarefas", "origem_id")
    op.drop_column("tarefas", "origem_tipo")
