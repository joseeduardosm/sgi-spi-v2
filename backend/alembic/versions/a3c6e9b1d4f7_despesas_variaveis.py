# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as colunas e a tabela das despesas variáveis da medição (itens marcados e documentos de despesa).
"""despesas variáveis na medição

- `contratos_competencias_itens.despesa_variavel`: item marcado como despesa variável na medição da competência;
- `contratos_competencias_memorias.anexo_despesas_id`: PDF da medição dos itens de despesas variáveis;
- `contratos_competencias_despesas_variaveis`: notas de débito, recibos e outros documentos juntados na etapa da nota fiscal.

Revision ID: a3c6e9b1d4f7
Revises: a7c3e9b5d1f2
Create Date: 2026-10-08 15:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a3c6e9b1d4f7"
down_revision: str | Sequence[str] | None = "a7c3e9b5d1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Nenhum item existente é despesa variável (nada muda até alguém marcar na medição)."""
    op.add_column("contratos_competencias_itens", sa.Column("despesa_variavel", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("contratos_competencias_memorias", sa.Column("anexo_despesas_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_memorias_anexo_despesas", "contratos_competencias_memorias", "anexos", ["anexo_despesas_id"], ["id"], ondelete="RESTRICT")
    op.create_table(
        "contratos_competencias_despesas_variaveis",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("competencia_id", sa.Uuid(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("numero", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("valor", sa.Numeric(18, 2), nullable=False),
        sa.Column("anexo_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("tipo IN ('nota_debito', 'recibo', 'outros')", name="ck_contratos_despesas_variaveis_tipo"),
        sa.ForeignKeyConstraint(["competencia_id"], ["contratos_competencias.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["anexo_id"], ["anexos.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("competencia_id", "ordem", name="uq_contratos_despesas_variaveis_competencia_ordem"),
    )
    op.create_index("ix_contratos_competencias_despesas_variaveis_competencia_id", "contratos_competencias_despesas_variaveis", ["competencia_id"])


def downgrade() -> None:
    """Remove a tabela e as colunas."""
    op.drop_index("ix_contratos_competencias_despesas_variaveis_competencia_id", table_name="contratos_competencias_despesas_variaveis")
    op.drop_table("contratos_competencias_despesas_variaveis")
    op.drop_constraint("fk_memorias_anexo_despesas", "contratos_competencias_memorias", type_="foreignkey")
    op.drop_column("contratos_competencias_memorias", "anexo_despesas_id")
    op.drop_column("contratos_competencias_itens", "despesa_variavel")
