# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas do marco 4 dos Chamados: TVs do painel e serviços do RH.

"""chamados: TVs do painel e categorias dos serviços do RH (marco 4)

- `chamados_paineis`: TV pareada (token em hash, IPs permitidos, voz) que mostra o painel de um setor e dos setores abaixo dele;
- `chamados_servicos_rh`: categoria de cada serviço pedido pelo RH na Nomeação;
- `chamados.servico_rh`: qual serviço do RH gerou o chamado (a admissão mostra o andamento de cada um).

Revision ID: 9e2c4a6b8d10
Revises: f8b0d2e4a6c9
Create Date: 2026-11-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "9e2c4a6b8d10"
down_revision: str | Sequence[str] | None = "f8b0d2e4a6c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGORA = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    """Cria as duas tabelas."""
    op.create_table(
        "chamados_paineis",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("setor_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("ips_permitidos", sa.String(500), nullable=False, server_default=""),
        sa.Column("voz", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("ultimo_acesso_em", sa.DateTime(timezone=True)),
        sa.Column("ultimo_ip", sa.String(45), nullable=False, server_default=""),
        sa.Column("criado_por_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
    )
    op.create_table(
        "chamados_servicos_rh",
        sa.Column("fluxo", sa.String(12), primary_key=True),
        sa.Column("servico", sa.String(30), primary_key=True),
        sa.Column("categoria_id", sa.Uuid, sa.ForeignKey("chamados_categorias.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("fluxo IN ('nomeacao')", name="ck_chamados_servicos_rh_fluxo"),
    )
    op.add_column("chamados", sa.Column("servico_rh", sa.String(30)))


def downgrade() -> None:
    """Remove a coluna e as duas tabelas."""
    op.drop_column("chamados", "servico_rh")
    op.drop_table("chamados_servicos_rh")
    op.drop_table("chamados_paineis")
