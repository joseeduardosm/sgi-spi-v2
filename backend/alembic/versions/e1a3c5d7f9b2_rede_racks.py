# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar o cadastro de racks da rede e ligar cada equipamento a um rack (no lugar do nome escrito à mão).

"""rede: racks (nome, cor, sala, altura em U) e o equipamento ligado ao rack

Os racks que já estavam escritos à mão nos equipamentos (`rede_equipamentos.rack`) viram cadastro (42U, cor preta, sem sala) e o texto sai.

Revision ID: e1a3c5d7f9b2
Revises: d7f9b1c3e5a8
Create Date: 2026-11-02
"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e1a3c5d7f9b2"
down_revision: str | Sequence[str] | None = "d7f9b1c3e5a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CORES = "'preto', 'cinza', 'azul', 'verde', 'amarelo', 'laranja', 'vermelho'"


def upgrade() -> None:
    """Cria os racks, leva o texto antigo para o cadastro e liga os equipamentos."""
    op.create_table(
        "rede_racks",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("nome", sa.String(80), nullable=False, unique=True),
        sa.Column("cor", sa.String(10), nullable=False, server_default="preto"),
        sa.Column("localizacao_id", sa.Uuid, sa.ForeignKey("patrimonio_localizacoes.id", ondelete="SET NULL")),
        sa.Column("altura_u", sa.Integer, nullable=False, server_default="42"),
        sa.Column("observacao", sa.Text, nullable=False, server_default=""),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(f"cor IN ({CORES})", name="ck_rede_racks_cor"),
        sa.CheckConstraint("altura_u BETWEEN 1 AND 60", name="ck_rede_racks_altura"),
    )
    op.add_column("rede_equipamentos", sa.Column("rack_id", sa.Uuid, sa.ForeignKey("rede_racks.id", ondelete="RESTRICT")))
    op.create_index("ix_rede_equipamentos_rack_id", "rede_equipamentos", ["rack_id"])
    conexao = op.get_bind()
    for (nome,) in conexao.execute(sa.text("SELECT DISTINCT trim(rack) FROM rede_equipamentos WHERE trim(rack) <> ''")).fetchall():
        rack_id = uuid.uuid4()
        conexao.execute(sa.text("INSERT INTO rede_racks (id, nome, cor, altura_u, observacao) VALUES (:id, :nome, 'preto', 42, '')"), {"id": rack_id, "nome": nome[:80]})
        conexao.execute(sa.text("UPDATE rede_equipamentos SET rack_id = :id WHERE trim(rack) = :nome"), {"id": rack_id, "nome": nome})
    op.drop_column("rede_equipamentos", "rack")


def downgrade() -> None:
    """Volta o nome do rack como texto no equipamento e apaga o cadastro."""
    op.add_column("rede_equipamentos", sa.Column("rack", sa.String(60), nullable=False, server_default=""))
    op.execute("UPDATE rede_equipamentos SET rack = (SELECT nome FROM rede_racks WHERE rede_racks.id = rede_equipamentos.rack_id) WHERE rack_id IS NOT NULL")
    op.drop_index("ix_rede_equipamentos_rack_id", table_name="rede_equipamentos")
    op.drop_column("rede_equipamentos", "rack_id")
    op.drop_table("rede_racks")
