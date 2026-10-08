# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar os estágios (colunas) configuráveis das equipes de tarefas, com os 4 padrão em cada equipe existente.
"""tarefas: estágios por equipe

Revision ID: c4d7e1f5a9b0
Revises: b3c6d0e4f8a9
Create Date: 2026-10-08 14:00:00
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d7e1f5a9b0"
down_revision: str | Sequence[str] | None = "b3c6d0e4f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PADRAO = (("A fazer", "a_fazer", 0), ("Em andamento", "em_andamento", 4), ("Em validação", "em_validacao", 5), ("Concluída", "concluida", 10))


def upgrade() -> None:
    """Tabela de estágios, coluna da tarefa e os 4 estágios padrão para cada equipe já cadastrada."""
    op.create_table(
        "tarefas_estagios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("equipe_id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=80), nullable=False),
        sa.Column("posicao", sa.Integer(), nullable=False),
        sa.Column("categoria", sa.String(length=15), nullable=False),
        sa.Column("cor_indice", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint("categoria IN ('a_fazer', 'em_andamento', 'em_validacao', 'concluida')", name="ck_tarefas_estagios_categoria"),
        sa.ForeignKeyConstraint(["equipe_id"], ["tarefas_equipes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipe_id", "nome", name="uq_tarefas_estagios_equipe_nome"),
    )
    op.create_index("ix_tarefas_estagios_equipe_id", "tarefas_estagios", ["equipe_id"])
    op.add_column("tarefas", sa.Column("estagio_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_tarefas_estagio", "tarefas", "tarefas_estagios", ["estagio_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_tarefas_estagio_id", "tarefas", ["estagio_id"])
    ligacao = op.get_bind()
    for (equipe_id,) in ligacao.execute(sa.text("SELECT id FROM tarefas_equipes")).all():
        for posicao, (nome, categoria, cor) in enumerate(PADRAO):
            ligacao.execute(
                sa.text("INSERT INTO tarefas_estagios (id, equipe_id, nome, posicao, categoria, cor_indice) VALUES (:id, :e, :n, :p, :c, :cor)"),
                {"id": uuid.uuid4(), "e": equipe_id, "n": nome, "p": posicao, "c": categoria, "cor": cor},
            )


def downgrade() -> None:
    """Remove os estágios (as tarefas voltam a ficar só pela situação)."""
    op.drop_index("ix_tarefas_estagio_id", table_name="tarefas")
    op.drop_constraint("fk_tarefas_estagio", "tarefas", type_="foreignkey")
    op.drop_column("tarefas", "estagio_id")
    op.drop_index("ix_tarefas_estagios_equipe_id", table_name="tarefas_estagios")
    op.drop_table("tarefas_estagios")
