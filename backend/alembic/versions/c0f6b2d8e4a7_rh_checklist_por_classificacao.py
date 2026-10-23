# Criado por José Eduardo Santana Martins
# Este arquivo serve para trocar o vínculo dos checklists de documentos: de tipo de cargo para classificação do cargo (grupo + nível).

"""rh: checklist por classificação do cargo (grupo e nível)

Revision ID: c0f6b2d8e4a7
Revises: b9e5a1c7d3f6
Create Date: 2026-10-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "c0f6b2d8e4a7"
down_revision: str | Sequence[str] | None = "b9e5a1c7d3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rh_checklist_classificacoes",
        sa.Column("checklist_id", sa.Integer(), sa.ForeignKey("rh_checklists.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("grupo", sa.SmallInteger(), primary_key=True),
        sa.Column("nivel", sa.SmallInteger(), primary_key=True),
    )
    op.add_column("rh_checklists", sa.Column("aplica_a_outros", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Quem estava ligado a um tipo passa a valer para todos os níveis daquele tipo que existem hoje no quadro (grupo e nível dos cargos cadastrados)
    conexao = op.get_bind()
    ligacoes = conexao.execute(sa.text("SELECT checklist_id, tipo_id FROM rh_checklist_tipos")).all()
    for checklist_id, tipo_id in ligacoes:
        pares = conexao.execute(sa.text("SELECT DISTINCT grupo, nivel FROM rh_cargos WHERE tipo_id = :t AND grupo IS NOT NULL AND nivel IS NOT NULL"), {"t": tipo_id}).all()
        for grupo, nivel in pares:
            conexao.execute(sa.text("INSERT INTO rh_checklist_classificacoes (checklist_id, grupo, nivel) SELECT :c, :g, :n WHERE NOT EXISTS "
                                    "(SELECT 1 FROM rh_checklist_classificacoes WHERE checklist_id = :c AND grupo = :g AND nivel = :n)"), {"c": checklist_id, "g": grupo, "n": nivel})
        codigo = conexao.execute(sa.text("SELECT codigo FROM rh_tipos_cargo WHERE id = :t"), {"t": tipo_id}).scalar()
        if codigo == "OUTRO":
            conexao.execute(sa.text("UPDATE rh_checklists SET aplica_a_outros = :v WHERE id = :c"), {"v": True, "c": checklist_id})
    op.drop_table("rh_checklist_tipos")


def downgrade() -> None:
    op.create_table(
        "rh_checklist_tipos",
        sa.Column("checklist_id", sa.Integer(), sa.ForeignKey("rh_checklists.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tipo_id", sa.Integer(), sa.ForeignKey("rh_tipos_cargo.id", ondelete="CASCADE"), primary_key=True),
    )
    with op.batch_alter_table("rh_checklists") as lote:
        lote.drop_column("aplica_a_outros")
    op.drop_table("rh_checklist_classificacoes")
