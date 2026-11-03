# Criado por José Eduardo Santana Martins
# Este arquivo serve para apagar a tabela das TVs pareadas (painel só com login) e preparar os chamados da Exoneração do RH.

"""chamados: painel só com login e chamados da Exoneração do RH

- Decisão do usuário: o painel é sempre de quem está logado e mostra os chamados em que o setor dela é o responsável.
  A tabela `chamados_paineis` (TVs com token) deixa de existir. A exibição do painel fica em `chamados_parametros` (chave/valor).
- Exoneração: `chamados_servicos_rh.fluxo` aceita `exoneracao` e o chamado guarda a ocupação encerrada (`rh_ocupacao_id`).

Revision ID: d7f9b1c3e5a8
Revises: c5e7a9b1d3f6
Create Date: 2026-11-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d7f9b1c3e5a8"
down_revision: str | Sequence[str] | None = "c5e7a9b1d3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apaga a tabela das TVs pareadas; abre o fluxo da Exoneração."""
    op.drop_table("chamados_paineis")
    op.drop_constraint("ck_chamados_servicos_rh_fluxo", "chamados_servicos_rh", type_="check")
    op.create_check_constraint("ck_chamados_servicos_rh_fluxo", "chamados_servicos_rh", "fluxo IN ('nomeacao', 'exoneracao')")
    op.add_column("chamados", sa.Column("rh_ocupacao_id", sa.Integer, sa.ForeignKey("rh_ocupacoes.id", ondelete="SET NULL")))
    op.create_index("ix_chamados_rh_ocupacao_id", "chamados", ["rh_ocupacao_id"])


def downgrade() -> None:
    """Desfaz a Exoneração e recria a tabela das TVs (vazia), como no marco 4."""
    op.drop_index("ix_chamados_rh_ocupacao_id", table_name="chamados")
    op.drop_column("chamados", "rh_ocupacao_id")
    op.execute("DELETE FROM chamados_servicos_rh WHERE fluxo = 'exoneracao'")
    op.drop_constraint("ck_chamados_servicos_rh_fluxo", "chamados_servicos_rh", type_="check")
    op.create_check_constraint("ck_chamados_servicos_rh_fluxo", "chamados_servicos_rh", "fluxo IN ('nomeacao')")
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
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
