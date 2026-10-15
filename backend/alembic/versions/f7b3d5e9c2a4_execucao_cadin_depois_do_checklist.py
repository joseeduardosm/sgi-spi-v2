# Criado por José Eduardo Santana Martins
# Este arquivo serve para ajustar as competências em andamento à nova ordem das etapas (retenção, checklist e só então CADIN).
"""contratos: CADIN passa a ser a última etapa antes do consolidado

Competências paradas em `cadin` com retenção ou checklist ainda pendentes voltam para a etapa pendente (o CADIN só abre com as anteriores prontas).

Revision ID: f7b3d5e9c2a4
Revises: e6a2c4d8b1f3
Create Date: 2026-10-15 15:00:00
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f7b3d5e9c2a4'
down_revision: Union[str, Sequence[str], None] = 'e6a2c4d8b1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE contratos_competencias SET etapa_atual = 'retencao' WHERE etapa_atual = 'cadin' AND retencao_concluida_em IS NULL")
    op.execute("UPDATE contratos_competencias SET etapa_atual = 'checklist' WHERE etapa_atual = 'cadin' AND checklist_concluido_em IS NULL")


def downgrade() -> None:
    pass
