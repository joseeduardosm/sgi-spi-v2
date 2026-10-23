# Criado por José Eduardo Santana Martins
# Este arquivo serve para permitir ocupações de cargo sem data de posse e limpar a data inventada dos vínculos automáticos do cadastro anterior.

"""rh: ocupação sem data de posse (vínculos automáticos)

Revision ID: f9a5b1c7d3e6
Revises: a1c5e9b3d7f4
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f9a5b1c7d3e6"
down_revision: str | Sequence[str] | None = "a1c5e9b3d7f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ATO_AUTOMATICO = "Vínculo do cadastro anterior"


def upgrade() -> None:
    """A data de posse passa a ser opcional; os vínculos automáticos do cadastro anterior (data inventada da criação do cadastro) ficam sem ela."""
    op.alter_column("rh_ocupacoes", "inicio", existing_type=sa.Date(), nullable=True)
    op.get_bind().execute(sa.text("UPDATE rh_ocupacoes SET inicio = NULL WHERE ato = :ato"), {"ato": ATO_AUTOMATICO})


def downgrade() -> None:
    """Sem data não existe na versão anterior: a data de registro da ocupação ocupa o lugar."""
    op.get_bind().execute(sa.text("UPDATE rh_ocupacoes SET inicio = CAST(registrado_em AS date) WHERE inicio IS NULL"))
    op.alter_column("rh_ocupacoes", "inicio", existing_type=sa.Date(), nullable=False)
