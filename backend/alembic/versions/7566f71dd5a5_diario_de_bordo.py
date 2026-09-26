# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas do diário de bordo e das glosas e o registro do e-mail da medição.
"""diário de bordo do contrato e glosas

- `contratos_diario_ocorrencias`: ocorrências relatadas pela equipe (imutáveis), com o resultado do e-mail
  enviado à equipe e ao preposto;
- `contratos_diario_glosas`: item e quantidade glosados por ocorrência;
- `contratos_competencias.email_medicao_*`: resultado do e-mail enviado ao concluir a medição.

Revision ID: 7566f71dd5a5
Revises: 3486e80ca434
Create Date: 2026-09-25 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão e a anterior (o Alembic encadeia as migrações por esses ids)
revision: str = "7566f71dd5a5"
down_revision: str | Sequence[str] | None = "3486e80ca434"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# JSON no SQLite (testes) e JSONB no PostgreSQL, como o `TipoJson` dos modelos
JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    """Cria as tabelas do diário e as colunas do e-mail da medição."""
    op.create_table(
        "contratos_diario_ocorrencias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contrato_id", sa.Uuid(), nullable=False),
        sa.Column("data_ocorrencia", sa.Date(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("possui_glosa", sa.Boolean(), nullable=False),
        sa.Column("registrada_por_id", sa.Integer(), nullable=True),
        sa.Column("registrada_por_nome", sa.String(length=250), nullable=False),
        sa.Column("registrada_por_papel", sa.String(length=40), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_ok", sa.Boolean(), nullable=True),
        sa.Column("email_destinatarios", JSON, nullable=False),
        sa.Column("email_erro", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["contrato_id"], ["contratos.id"], ondelete="CASCADE",
                                name="contratos_diario_ocorrencias_contrato_id_fkey"),
        sa.ForeignKeyConstraint(["registrada_por_id"], ["usuarios.id"], ondelete="SET NULL",
                                name="contratos_diario_ocorrencias_registrada_por_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="contratos_diario_ocorrencias_pkey"),
    )
    op.create_index("ix_contratos_diario_ocorrencias_contrato_id", "contratos_diario_ocorrencias", ["contrato_id"])
    op.create_index("ix_contratos_diario_ocorrencias_data_ocorrencia", "contratos_diario_ocorrencias", ["data_ocorrencia"])

    op.create_table(
        "contratos_diario_glosas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ocorrencia_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("descricao_item", sa.String(length=1000), nullable=False),
        sa.Column("quantidade", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.CheckConstraint("quantidade > 0", name="ck_contratos_diario_glosas_quantidade"),
        sa.ForeignKeyConstraint(["item_id"], ["contratos_itens.id"], ondelete="CASCADE", name="contratos_diario_glosas_item_id_fkey"),
        sa.ForeignKeyConstraint(["ocorrencia_id"], ["contratos_diario_ocorrencias.id"], ondelete="CASCADE",
                                name="contratos_diario_glosas_ocorrencia_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="contratos_diario_glosas_pkey"),
        sa.UniqueConstraint("ocorrencia_id", "item_id", name="contratos_diario_glosas_ocorrencia_id_item_id_key"),
    )
    op.create_index("ix_contratos_diario_glosas_item_id", "contratos_diario_glosas", ["item_id"])
    op.create_index("ix_contratos_diario_glosas_ocorrencia_id", "contratos_diario_glosas", ["ocorrencia_id"])

    # Competências existentes começam sem e-mail enviado (lista de destinatários vazia)
    op.add_column("contratos_competencias", sa.Column("email_medicao_enviado_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contratos_competencias", sa.Column("email_medicao_ok", sa.Boolean(), nullable=True))
    op.add_column("contratos_competencias", sa.Column("email_medicao_destinatarios", JSON, nullable=False, server_default=sa.text("'[]'")))
    op.add_column("contratos_competencias", sa.Column("email_medicao_erro", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove as colunas do e-mail da medição e as tabelas do diário (as glosas saem junto)."""
    op.drop_column("contratos_competencias", "email_medicao_erro")
    op.drop_column("contratos_competencias", "email_medicao_destinatarios")
    op.drop_column("contratos_competencias", "email_medicao_ok")
    op.drop_column("contratos_competencias", "email_medicao_enviado_em")
    op.drop_index("ix_contratos_diario_glosas_ocorrencia_id", table_name="contratos_diario_glosas")
    op.drop_index("ix_contratos_diario_glosas_item_id", table_name="contratos_diario_glosas")
    op.drop_table("contratos_diario_glosas")
    op.drop_index("ix_contratos_diario_ocorrencias_data_ocorrencia", table_name="contratos_diario_ocorrencias")
    op.drop_index("ix_contratos_diario_ocorrencias_contrato_id", table_name="contratos_diario_ocorrencias")
    op.drop_table("contratos_diario_ocorrencias")
