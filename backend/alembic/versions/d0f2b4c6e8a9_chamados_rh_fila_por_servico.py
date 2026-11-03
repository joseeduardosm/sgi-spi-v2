# Criado por José Eduardo Santana Martins
# Este arquivo serve para configurar cada serviço do RH pela fila (setor), prioridade e prazos, sem precisar de um assunto por serviço.

"""chamados: serviço do RH com fila, prioridade e SLAs próprios (o assunto por serviço sai de uso)

Revision ID: d0f2b4c6e8a9
Revises: c8e0a2b4d6f7
Create Date: 2026-11-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d0f2b4c6e8a9"
down_revision: str | Sequence[str] | None = "c8e0a2b4d6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fila, prioridade e SLAs por serviço; a categoria por serviço vira opcional (regra antiga)."""
    with op.batch_alter_table("chamados_servicos_rh") as tabela:
        tabela.alter_column("categoria_id", existing_type=sa.Uuid, nullable=True)
        tabela.add_column(sa.Column("setor_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="SET NULL", name="fk_chamados_servicos_rh_setor")))
        tabela.add_column(sa.Column("prioridade", sa.String(7), nullable=False, server_default="normal"))
        tabela.add_column(sa.Column("sla_tto_id", sa.Uuid, sa.ForeignKey("chamados_slas.id", ondelete="SET NULL", name="fk_chamados_servicos_rh_tto")))
        tabela.add_column(sa.Column("sla_ttr_id", sa.Uuid, sa.ForeignKey("chamados_slas.id", ondelete="SET NULL", name="fk_chamados_servicos_rh_ttr")))
        tabela.create_check_constraint("ck_chamados_servicos_rh_prioridade", "prioridade IN ('baixa', 'normal', 'alta', 'urgente')")


def downgrade() -> None:
    with op.batch_alter_table("chamados_servicos_rh") as tabela:
        tabela.drop_constraint("ck_chamados_servicos_rh_prioridade", type_="check")
        tabela.drop_column("sla_ttr_id")
        tabela.drop_column("sla_tto_id")
        tabela.drop_column("prioridade")
        tabela.drop_column("setor_id")
