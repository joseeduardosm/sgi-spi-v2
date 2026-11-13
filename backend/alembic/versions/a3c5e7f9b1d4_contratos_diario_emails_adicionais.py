# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar os e-mails adicionais das ocorrências do diário e a escolha de destinatários de cada ocorrência.

"""contratos: e-mails adicionais nas ocorrências do diário de bordo

- `contratos_diario_emails_salvos`: e-mails adicionais já usados nas ocorrências de um contrato (um por contrato, em minúsculas),
  oferecidos desmarcados nas próximas ocorrências daquele contrato.
- `contratos_diario_ocorrencias.email_prepostos_ids` e `email_adicionais`: quem foi escolhido para receber no registro, para o
  reenvio repetir a mesma escolha. Registros antigos ficam nulos (o reenvio continua indo a todos os prepostos ativos).

Revision ID: a3c5e7f9b1d4
Revises: e2a4c6e8f0b1
Create Date: 2026-11-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão e a anterior
revision: str = "a3c5e7f9b1d4"
down_revision: str | Sequence[str] | None = "e2a4c6e8f0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# JSON no SQLite, JSONB no PostgreSQL (mesmo tipo do modelo)
JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "contratos_diario_emails_salvos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contrato_id", sa.Uuid(), sa.ForeignKey("contratos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(250), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("contrato_id", "email", name="contratos_diario_emails_salvos_contrato_email_key"),
    )
    op.create_index("ix_contratos_diario_emails_salvos_contrato_id", "contratos_diario_emails_salvos", ["contrato_id"])
    op.add_column("contratos_diario_ocorrencias", sa.Column("email_prepostos_ids", JSON, nullable=True))
    op.add_column("contratos_diario_ocorrencias", sa.Column("email_adicionais", JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("contratos_diario_ocorrencias", "email_adicionais")
    op.drop_column("contratos_diario_ocorrencias", "email_prepostos_ids")
    op.drop_index("ix_contratos_diario_emails_salvos_contrato_id", table_name="contratos_diario_emails_salvos")
    op.drop_table("contratos_diario_emails_salvos")
