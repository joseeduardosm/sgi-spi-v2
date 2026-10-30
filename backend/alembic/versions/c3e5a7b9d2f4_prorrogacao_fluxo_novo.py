# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a escolha dos meses quebrados, a memória de cálculo e o checklist do fluxo novo da prorrogação.
"""prorrogação: meses quebrados, memória de cálculo e checklist

- `contratos_prorrogacoes_processos.calculo_mes_quebrado`: pro rata ou integral nos meses quebrados da nova vigência;
- `contratos_prorrogacoes_memorias`: PDF e XLSX da memória de cálculo, versionados pelo hash dos dados;
- `contratos_prorrogacoes_documentos`: checklist da prorrogação (copiado do modelo ou incluído durante o processo);
- `contratos_modelos.tipo` passa a aceitar `checklist_prorrogacao` (coluna alargada para 30).

Revision ID: c3e5a7b9d2f4
Revises: b8d2f4a6c9e1
Create Date: 2026-10-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# ────────────────────────────────────────────────────────────────────────────
revision = "c3e5a7b9d2f4"
down_revision = "b8d2f4a6c9e1"
branch_labels = None
depends_on = None
# ────────────────────────────────────────────────────────────────────────────

TIPOS_ANTES = "('checklist', 'formulario', 'portaria', 'despacho', 'email_cadin', 'email_ob', 'prorrogacao')"
TIPOS_DEPOIS = "('checklist', 'formulario', 'portaria', 'despacho', 'email_cadin', 'email_ob', 'prorrogacao', 'checklist_prorrogacao')"


def upgrade() -> None:
    op.add_column("contratos_prorrogacoes_processos", sa.Column("calculo_mes_quebrado", sa.String(10), nullable=True,
                                                                comment="Meses quebrados da nova vigência: pro_rata ou integral; nulo = ainda não escolhido."))

    op.create_table(
        "contratos_prorrogacoes_memorias",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("processo_id", UUID(as_uuid=True), sa.ForeignKey("contratos_prorrogacoes_processos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("pdf_anexo_id", UUID(as_uuid=True), sa.ForeignKey("anexos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("xlsx_anexo_id", UUID(as_uuid=True), sa.ForeignKey("anexos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("hash_origem", sa.String(64), nullable=False),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("processo_id", "versao"),
    )

    op.create_table(
        "contratos_prorrogacoes_documentos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("processo_id", UUID(as_uuid=True), sa.ForeignKey("contratos_prorrogacoes_processos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(500), nullable=False),
        sa.Column("observacao", sa.String(1000), nullable=False, server_default=""),
        sa.Column("obrigatorio", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("anexo_id", UUID(as_uuid=True), sa.ForeignKey("anexos.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enviado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("incluido_no_processo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("incluido_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("incluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("processo_id", "ordem"),
    )

    op.alter_column("contratos_modelos", "tipo", type_=sa.String(30), existing_type=sa.String(20))
    op.drop_constraint("ck_contratos_modelos_tipo", "contratos_modelos", type_="check")
    op.create_check_constraint("ck_contratos_modelos_tipo", "contratos_modelos", f"tipo IN {TIPOS_DEPOIS}")


def downgrade() -> None:
    op.execute("DELETE FROM contratos_modelos WHERE tipo = 'checklist_prorrogacao'")
    op.drop_constraint("ck_contratos_modelos_tipo", "contratos_modelos", type_="check")
    op.create_check_constraint("ck_contratos_modelos_tipo", "contratos_modelos", f"tipo IN {TIPOS_ANTES}")
    op.alter_column("contratos_modelos", "tipo", type_=sa.String(20), existing_type=sa.String(30))
    op.drop_table("contratos_prorrogacoes_documentos")
    op.drop_table("contratos_prorrogacoes_memorias")
    op.drop_column("contratos_prorrogacoes_processos", "calculo_mes_quebrado")
