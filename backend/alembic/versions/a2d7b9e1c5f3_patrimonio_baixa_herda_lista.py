# Criado por José Eduardo Santana Martins
# Este arquivo serve para a nova regra da Baixa de bens: herda uma lista aprovada, aguarda o aceite da autoridade e conclui com o PDF (D.O.E.).

"""patrimônio: baixa herda uma lista de inservíveis e conclui com o PDF do de acordo da autoridade

Revision ID: a2d7b9e1c5f3
Revises: f1c6a8d2e4b7
Create Date: 2026-10-20
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a2d7b9e1c5f3"
down_revision: str | Sequence[str] | None = "f1c6a8d2e4b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Novas colunas, status mais longo e conversão dos status antigos (pendente → aguardando_aceite; aprovada/parcial → concluida, sem PDF)."""
    op.alter_column("patrimonio_baixas", "status", existing_type=sa.String(10), type_=sa.String(20), existing_nullable=False)
    op.add_column("patrimonio_baixas", sa.Column("classificacao_origem_id", sa.Uuid(), nullable=True))
    op.add_column("patrimonio_baixas", sa.Column("doe_anexo_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_baixas_classificacao_origem", "patrimonio_baixas", "patrimonio_classificacoes", ["classificacao_origem_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_baixas_doe_anexo", "patrimonio_baixas", "anexos", ["doe_anexo_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_patrimonio_baixas_classificacao_origem_id", "patrimonio_baixas", ["classificacao_origem_id"])
    op.execute(sa.text("UPDATE patrimonio_baixas SET status = 'aguardando_aceite' WHERE status = 'pendente'"))
    op.execute(sa.text("UPDATE patrimonio_baixas SET status = 'concluida' WHERE status IN ('aprovada', 'parcial')"))


def downgrade() -> None:
    """Volta aos status antigos (concluida → aprovada; aguardando_aceite → pendente)."""
    op.execute(sa.text("UPDATE patrimonio_baixas SET status = 'aprovada' WHERE status = 'concluida'"))
    op.execute(sa.text("UPDATE patrimonio_baixas SET status = 'pendente' WHERE status = 'aguardando_aceite'"))
    op.drop_index("ix_patrimonio_baixas_classificacao_origem_id", table_name="patrimonio_baixas")
    op.drop_constraint("fk_baixas_doe_anexo", "patrimonio_baixas", type_="foreignkey")
    op.drop_constraint("fk_baixas_classificacao_origem", "patrimonio_baixas", type_="foreignkey")
    op.drop_column("patrimonio_baixas", "doe_anexo_id")
    op.drop_column("patrimonio_baixas", "classificacao_origem_id")
    op.alter_column("patrimonio_baixas", "status", existing_type=sa.String(20), type_=sa.String(10), existing_nullable=False)
