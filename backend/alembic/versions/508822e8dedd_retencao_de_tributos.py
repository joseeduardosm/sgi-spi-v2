# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a etapa "Retenção de Tributos" e guardar o XML da nota fiscal nas competências.
"""execução: etapa de retenção de tributos e XML da nota fiscal

- nova etapa `retencao` entre `nota_fiscal` e `cadin` (CHECK das etapas refeito);
- XML da NF principal e da adicional (anexo, dados lidos e chave), retenção de CSLL;
- quem conferiu a retenção, quando, e o PDF gerado; resultado dos e-mails da NF e da retenção.

Competências que já passaram da nota fiscal no fluxo antigo (retenções lançadas junto com a NF) ficam com a
retenção dada como conferida na mesma data da NF.

Revision ID: 508822e8dedd
Revises: 7566f71dd5a5
Create Date: 2026-09-25 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão e a anterior (o Alembic encadeia as migrações por esses ids)
revision: str = "508822e8dedd"
down_revision: str | Sequence[str] | None = "7566f71dd5a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
TABELA = "contratos_competencias"
ETAPAS_ANTIGAS = "'medicao', 'avaliacao', 'nota_fiscal', 'cadin', 'checklist', 'consolidado', 'ordem_bancaria', 'concluida'"
ETAPAS_NOVAS = "'medicao', 'avaliacao', 'nota_fiscal', 'retencao', 'cadin', 'checklist', 'consolidado', 'ordem_bancaria', 'concluida'"
# (coluna, tabela de destino, ação ao excluir)
CHAVES = (
    ("nf_xml_anexo_id", "anexos", "RESTRICT"),
    ("nf_adicional_xml_anexo_id", "anexos", "RESTRICT"),
    ("retencao_pdf_anexo_id", "anexos", "RESTRICT"),
    ("retencao_por_id", "usuarios", "SET NULL"),
)


def upgrade() -> None:
    """Colunas novas, chaves, índices, CHECK das etapas e a retenção das competências antigas."""
    colunas = [
        sa.Column("nf_retencao_csll", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("nf_xml_anexo_id", sa.Uuid(), nullable=True),
        sa.Column("nf_dados_xml", JSON, nullable=True),
        sa.Column("nf_chave", sa.String(60), nullable=True),
        sa.Column("nf_adicional_retencao_csll", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("nf_adicional_xml_anexo_id", sa.Uuid(), nullable=True),
        sa.Column("nf_adicional_dados_xml", JSON, nullable=True),
        sa.Column("nf_adicional_chave", sa.String(60), nullable=True),
        sa.Column("retencao_concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retencao_por_id", sa.Integer(), nullable=True),
        sa.Column("retencao_por_nome", sa.String(250), server_default="", nullable=False),
        sa.Column("retencao_discriminacao_conferida", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("retencao_pdf_anexo_id", sa.Uuid(), nullable=True),
        sa.Column("email_nf_enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_nf_ok", sa.Boolean(), nullable=True),
        sa.Column("email_nf_destinatarios", JSON, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("email_nf_erro", sa.Text(), nullable=True),
        sa.Column("email_retencao_enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_retencao_ok", sa.Boolean(), nullable=True),
        sa.Column("email_retencao_destinatarios", JSON, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("email_retencao_erro", sa.Text(), nullable=True),
    ]
    for coluna in colunas:
        op.add_column(TABELA, coluna)
    op.create_index("ix_contratos_competencias_nf_chave", TABELA, ["nf_chave"])
    op.create_index("ix_contratos_competencias_nf_adicional_chave", TABELA, ["nf_adicional_chave"])
    for coluna, destino, acao in CHAVES:
        op.create_foreign_key(f"{TABELA}_{coluna}_fkey", TABELA, destino, [coluna], ["id"], ondelete=acao)
    op.drop_constraint("ck_contratos_competencias_etapa", TABELA, type_="check")
    op.create_check_constraint("ck_contratos_competencias_etapa", TABELA, f"etapa_atual IN ({ETAPAS_NOVAS})")
    # Fluxo antigo: as retenções foram lançadas junto com a NF; quem já passou da NF tem a retenção cumprida
    op.execute(
        f"UPDATE {TABELA} SET retencao_concluida_em = nf_concluida_em "
        "WHERE nf_concluida_em IS NOT NULL AND etapa_atual IN ('cadin', 'checklist', 'consolidado', 'ordem_bancaria', 'concluida')"
    )


def downgrade() -> None:
    """Volta ao fluxo sem a etapa de retenção (quem está nela segue para o CADIN)."""
    op.execute(f"UPDATE {TABELA} SET etapa_atual = 'cadin' WHERE etapa_atual = 'retencao'")
    op.drop_constraint("ck_contratos_competencias_etapa", TABELA, type_="check")
    op.create_check_constraint("ck_contratos_competencias_etapa", TABELA, f"etapa_atual IN ({ETAPAS_ANTIGAS})")
    for coluna, _, _ in CHAVES:
        op.drop_constraint(f"{TABELA}_{coluna}_fkey", TABELA, type_="foreignkey")
    op.drop_index("ix_contratos_competencias_nf_adicional_chave", table_name=TABELA)
    op.drop_index("ix_contratos_competencias_nf_chave", table_name=TABELA)
    for coluna in (
        "email_retencao_erro", "email_retencao_destinatarios", "email_retencao_ok", "email_retencao_enviado_em",
        "email_nf_erro", "email_nf_destinatarios", "email_nf_ok", "email_nf_enviado_em",
        "retencao_pdf_anexo_id", "retencao_discriminacao_conferida", "retencao_por_nome", "retencao_por_id", "retencao_concluida_em",
        "nf_adicional_chave", "nf_adicional_dados_xml", "nf_adicional_xml_anexo_id", "nf_adicional_retencao_csll",
        "nf_chave", "nf_dados_xml", "nf_xml_anexo_id", "nf_retencao_csll",
    ):
        op.drop_column(TABELA, coluna)
