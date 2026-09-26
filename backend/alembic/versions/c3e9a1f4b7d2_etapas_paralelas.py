# Criado por José Eduardo Santana Martins
# Este arquivo serve para registrar a conclusão do CADIN e do checklist, que passam a correr em paralelo com a retenção.
"""execução: retenção, CADIN e checklist em paralelo

Depois da nota fiscal, retenção de tributos, CADIN e checklist ficam abertos ao mesmo tempo; o documento
consolidado só é liberado com os três concluídos. Como `etapa_atual` deixa de dizer sozinha o que já foi
feito, cada uma das duas etapas ganha a data de conclusão (a retenção já tem `retencao_concluida_em`).

Competências que já passaram de cada etapa ficam com ela concluída (na data do consolidado ou, na falta,
agora).

Revision ID: c3e9a1f4b7d2
Revises: 508822e8dedd
Create Date: 2026-09-25 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior (o Alembic encadeia as migrações por esses ids)
revision: str = "c3e9a1f4b7d2"
down_revision: str | Sequence[str] | None = "508822e8dedd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELA = "contratos_competencias"


def upgrade() -> None:
    """Colunas de conclusão e preenchimento para quem já passou das etapas."""
    op.add_column(TABELA, sa.Column("cadin_concluido_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABELA, sa.Column("checklist_concluido_em", sa.DateTime(timezone=True), nullable=True))
    depois_do_checklist = "('consolidado', 'ordem_bancaria', 'concluida')"
    op.execute(f"UPDATE {TABELA} SET cadin_concluido_em = COALESCE(consolidado_em, CURRENT_TIMESTAMP) "
               f"WHERE etapa_atual IN ('checklist', 'consolidado', 'ordem_bancaria', 'concluida')")
    op.execute(f"UPDATE {TABELA} SET checklist_concluido_em = COALESCE(consolidado_em, CURRENT_TIMESTAMP) WHERE etapa_atual IN {depois_do_checklist}")


def downgrade() -> None:
    """Remove as colunas (o fluxo volta a ser apenas sequencial)."""
    op.drop_column(TABELA, "checklist_concluido_em")
    op.drop_column(TABELA, "cadin_concluido_em")
