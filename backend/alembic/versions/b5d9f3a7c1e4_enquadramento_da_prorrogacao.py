# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar o checklist do Parecer Referencial (enquadramento) no rascunho e na prorrogação registrada.
"""enquadramento da prorrogação no Parecer Referencial

- `contratos_prorrogacoes_processos.enquadramento` (JSON): as respostas da equipe aos 37 itens;
- `contratos_prorrogacoes.enquadramento` (JSON): fotografia no registro (respostas, o que valia em cada item e se precisava de análise jurídica).

Revision ID: b5d9f3a7c1e4
Revises: a4c8e2f6b0d3
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from alembic import op

revision = "b5d9f3a7c1e4"
down_revision = "a4c8e2f6b0d3"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    for tabela in ("contratos_prorrogacoes_processos", "contratos_prorrogacoes"):
        op.add_column(tabela, sa.Column("enquadramento", JSON, nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    for tabela in ("contratos_prorrogacoes", "contratos_prorrogacoes_processos"):
        op.drop_column(tabela, "enquadramento")
