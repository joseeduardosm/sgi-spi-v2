# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar a descrição (orientação) de cada seção dos documentos de Contratações, mostrada só na tela.
"""contratações: descrição (orientação) da seção

Texto que orienta quem preenche a seção. Só aparece na tela: não vai para a cópia da seção nem para o Word/PDF.

Revision ID: a7c3e9b5d1f4
Revises: f2b8d4a6c1e3
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa

# ────────────────────────────────────────────────────────────────────────────
revision = "a7c3e9b5d1f4"
down_revision = "f2b8d4a6c1e3"
branch_labels = None
depends_on = None
# ────────────────────────────────────────────────────────────────────────────


def upgrade() -> None:
    op.add_column(
        "contratacoes_secoes",
        sa.Column("descricao", sa.Text(), nullable=False, server_default="",
                  comment="Orientação a quem preenche a seção; só aparece na tela."),
    )


def downgrade() -> None:
    op.drop_column("contratacoes_secoes", "descricao")
