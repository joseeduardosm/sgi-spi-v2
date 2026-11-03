# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas do marco 6 dos Chamados: satisfação, respostas prontas e motivos de pendência.

"""chamados: satisfação, respostas prontas e motivos de pendência (marco 6)

- `chamados_satisfacao`: nota de 1 a 5 do solicitante (uma por chamado);
- `chamados_respostas_prontas`: textos prontos de quem atende (por setor ou para todos);
- `chamados_motivos_pendencia`: motivos padronizados do "Pendente".

Revision ID: b3d5f7a9c1e4
Revises: 9e2c4a6b8d10
Create Date: 2026-11-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b3d5f7a9c1e4"
down_revision: str | Sequence[str] | None = "9e2c4a6b8d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGORA = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    """Cria as três tabelas."""
    op.create_table(
        "chamados_satisfacao",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("chamado_id", sa.Uuid, sa.ForeignKey("chamados.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("nota", sa.SmallInteger),
        sa.Column("comentario", sa.Text, nullable=False, server_default=""),
        sa.Column("pedida_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.Column("respondida_em", sa.DateTime(timezone=True)),
        sa.Column("respondida_por_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("origem_glpi_id", sa.Integer),
        sa.CheckConstraint("nota IS NULL OR nota BETWEEN 1 AND 5", name="ck_chamados_satisfacao_nota"),
    )
    op.create_table(
        "chamados_respostas_prontas",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("titulo", sa.String(120), nullable=False),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("setor_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="CASCADE"), index=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("ordem", sa.Integer, nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
    )
    op.create_table(
        "chamados_motivos_pendencia",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False, unique=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("ordem", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Remove as três tabelas."""
    for tabela in ("chamados_motivos_pendencia", "chamados_respostas_prontas", "chamados_satisfacao"):
        op.drop_table(tabela)
