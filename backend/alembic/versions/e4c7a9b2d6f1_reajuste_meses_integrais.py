# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar quais meses fracionados o gestor marcou para entrar inteiros na
# diferença do reajuste.
"""reajuste: meses_integrais

Guarda quais meses cortados (virada de vigência ou data de efeito) o gestor marcou para
entrar inteiros na diferença retroativa. Lista vazia preserva o comportamento automático,
então não há backfill.

Revision ID: e4c7a9b2d6f1
Revises: d1e3f5a7b9c2
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# ────────────────────────────────────────────────────────────────────────────
revision = "e4c7a9b2d6f1"
down_revision = "d1e3f5a7b9c2"
branch_labels = None
depends_on = None
# ────────────────────────────────────────────────────────────────────────────


def upgrade() -> None:
    op.add_column(
        "contratos_reajustes",
        sa.Column(
            "meses_integrais",
            JSONB(),
            nullable=False,
            server_default="[]",
            comment='Meses cortados marcados para entrar inteiros na diferença, como "AAAA-MM"; vazio = regra automática.',
        ),
    )


def downgrade() -> None:
    op.drop_column("contratos_reajustes", "meses_integrais")
