# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela dos e-mails de changelog enviados pela mensageria (conta root).
"""mensageria: envios do e-mail de changelog

- `mensageria_envios_changelog`: cada e-mail de novidades enviado (a todos ou de teste), com o assunto e o texto
  editados, a data da entrada mais recente do CHANGELOG incluída e o resultado do envio.

Revision ID: 7a3c5e9f1b2d
Revises: 5de0447b97ad
Create Date: 2026-09-29 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "7a3c5e9f1b2d"
down_revision: str | Sequence[str] | None = "5de0447b97ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria a tabela dos envios."""
    op.create_table(
        "mensageria_envios_changelog",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assunto", sa.String(length=300), nullable=False),
        sa.Column("corpo", sa.Text(), nullable=False),
        sa.Column("ate_data", sa.Date(), nullable=True),
        sa.Column("destino", sa.String(length=10), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("enviados", sa.Integer(), nullable=False),
        sa.Column("falhas", sa.Integer(), nullable=False),
        sa.Column("erros", sa.Text(), nullable=True),
        sa.Column("enviado_por_id", sa.Integer(), nullable=True),
        sa.Column("enviado_por_nome", sa.String(length=200), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("destino IN ('todos', 'teste')", name="ck_mensageria_envios_changelog_destino"),
        sa.ForeignKeyConstraint(["enviado_por_id"], ["usuarios.id"], name="mensageria_envios_changelog_enviado_por_id_fkey", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="mensageria_envios_changelog_pkey"),
    )


def downgrade() -> None:
    """Remove a tabela dos envios."""
    op.drop_table("mensageria_envios_changelog")
