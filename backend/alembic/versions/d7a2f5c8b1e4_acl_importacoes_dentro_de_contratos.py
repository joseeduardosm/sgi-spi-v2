# Criado por José Eduardo Santana Martins
# Este arquivo serve para tirar da ACL os recursos de importação por planilha, agora embutidos em Contratos.

"""acl: importações XLSX passam a fazer parte de "Editar contratos e conduzir a execução"

Revision ID: d7a2f5c8b1e4
Revises: c5e1a7d3f9b6
Create Date: 2026-10-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d7a2f5c8b1e4"
down_revision: str | Sequence[str] | None = "c5e1a7d3f9b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUGS = ("importacao-contratos", "importacao-modelos")


def upgrade() -> None:
    """Remove os dois recursos; regras, vínculos e direitos de perfil saem em cascata.

    Quem importava já precisava de `contratos` ≥ MODIFICACAO, que agora basta.
    """
    for slug in SLUGS:
        op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :slug").bindparams(slug=slug))


def downgrade() -> None:
    """Não recria os recursos: a importação não os usa mais (recriá-los pela tela de ACL não tem efeito)."""
