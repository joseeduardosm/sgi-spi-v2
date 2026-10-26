# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a integração com o SIGEO, o processo financeiro do contrato e os dados da ordem bancária na competência.

"""sigeo: integração, processo financeiro do contrato e dados da OB na competência

Revision ID: e5a9c3f7b1d4
Revises: d4f8b2a6c0e3
Create Date: 2026-10-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e5a9c3f7b1d4"
down_revision: str | Sequence[str] | None = "d4f8b2a6c0e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integracao_sigeo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("url_base", sa.String(length=300), nullable=False, server_default="https://www.sigeo.fazenda.sp.gov.br/analytics/saw.dll"),
        sa.Column("caminho_analise", sa.String(length=500), nullable=False, server_default="/users/31818707810/SPI - Execução/PAGO - Execução Contrato - Gestor"),
        sa.Column("usuario", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("senha_cifrada", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("ultima_execucao_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_resultado", sa.JSON(), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_por", sa.String(length=200), nullable=False, server_default=""),
    )
    op.add_column("contratos", sa.Column("processo_financeiro", sa.String(length=60), nullable=False, server_default=""))
    for nome, tipo in (("ob_origem", sa.String(length=10)), ("ob_numero", sa.String(length=300)), ("ob_data", sa.Date()), ("ob_valor", sa.Numeric(18, 2)),
                       ("ob_descricao_sigeo", sa.Text()), ("ob_sigeo_pendencia", sa.Text()), ("ob_sigeo_verificado_em", sa.DateTime(timezone=True))):
        op.add_column("contratos_competencias", sa.Column(nome, tipo, nullable=True))
    # As OBs já juntadas foram lançadas à mão (PDF)
    op.execute(sa.text("UPDATE contratos_competencias SET ob_origem = 'manual' WHERE ob_anexo_id IS NOT NULL"))


def downgrade() -> None:
    for nome in ("ob_sigeo_verificado_em", "ob_sigeo_pendencia", "ob_descricao_sigeo", "ob_valor", "ob_data", "ob_numero", "ob_origem"):
        op.drop_column("contratos_competencias", nome)
    op.drop_column("contratos", "processo_financeiro")
    op.drop_table("integracao_sigeo")
