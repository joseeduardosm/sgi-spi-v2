# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar o prazo de contestação da medição (dias úteis) e o documento executivo enviado à contratada.

"""contratos: comunicação única da medição, prazo de contestação em dias úteis e documento executivo

Revision ID: c4f9a2d7e1b8
Revises: b3e8d1f6a9c4
Create Date: 2026-10-20
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# JSON no SQLite (testes) e JSONB no PostgreSQL, como o `TipoJson` dos modelos
JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

# Identificação da migração: esta revisão e a anterior
revision: str = "c4f9a2d7e1b8"
down_revision: str | Sequence[str] | None = "b3e8d1f6a9c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Colunas novas e opcionais: as competências já enviadas ficam sem prazo de contestação (valem as 48 h da regra anterior)."""
    op.add_column("contratos_competencias", sa.Column("medicao_envio_solicitado", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("contratos_competencias", sa.Column("medicao_envio_prepostos", JSON, nullable=True))
    op.add_column("contratos_competencias", sa.Column("prazo_contestacao_dias", sa.Integer(), nullable=True))
    op.add_column("contratos_competencias", sa.Column("contestacao_inicio_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contratos_competencias", sa.Column("contestacao_limite_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contratos_competencias", sa.Column("documento_executivo_anexo_id", sa.Uuid(), nullable=True))
    op.add_column("contratos_competencias", sa.Column("documento_executivo_versao", sa.Integer(), nullable=False, server_default="0"))
    op.create_foreign_key("fk_competencia_doc_executivo", "contratos_competencias", "anexos", ["documento_executivo_anexo_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint("fk_competencia_doc_executivo", "contratos_competencias", type_="foreignkey")
    for coluna in ("documento_executivo_versao", "documento_executivo_anexo_id", "contestacao_limite_em", "contestacao_inicio_em",
                   "prazo_contestacao_dias", "medicao_envio_prepostos", "medicao_envio_solicitado"):
        op.drop_column("contratos_competencias", coluna)
