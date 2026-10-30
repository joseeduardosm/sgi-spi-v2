# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar na prorrogação registrada o prazo e a publicação no PNCP, o DOE, a garantia e a atualização do Contratos.gov.
"""pós-assinatura da prorrogação

Colunas novas em `contratos_prorrogacoes` (todas opcionais, aditivas): `pncp_prazo_ate`, `pncp_publicado_em`, `pncp_numero`, `doe_publicado_em`,
`garantia_comprovada_em`, `garantia_enviada_dof_em`, `dados_garantia` (JSON) e `contratos_gov_atualizado_em`.

Revision ID: c6e0a4b8d2f5
Revises: b5d9f3a7c1e4
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "c6e0a4b8d2f5"
down_revision = "b5d9f3a7c1e4"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql")
DATAS = ("pncp_prazo_ate", "pncp_publicado_em", "doe_publicado_em", "garantia_comprovada_em", "garantia_enviada_dof_em", "contratos_gov_atualizado_em")


def upgrade() -> None:
    for coluna in DATAS:
        op.add_column("contratos_prorrogacoes", sa.Column(coluna, sa.Date(), nullable=True))
    op.add_column("contratos_prorrogacoes", sa.Column("pncp_numero", sa.String(100), nullable=False, server_default=""))
    op.add_column("contratos_prorrogacoes", sa.Column("dados_garantia", JSON, nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    for coluna in ("dados_garantia", "pncp_numero", *DATAS):
        op.drop_column("contratos_prorrogacoes", coluna)
