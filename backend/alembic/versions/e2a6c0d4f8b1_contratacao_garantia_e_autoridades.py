# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar a origem da contratação e a garantia no contrato, o representante legal da empresa e os parâmetros da prorrogação.

"""contratos: modalidade, garantia, representante legal e parâmetros da prorrogação

Revision ID: e2a6c0d4f8b1
Revises: d1f5b9c3e7a4
Create Date: 2026-10-27
"""
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e2a6c0d4f8b1"
down_revision: str | Sequence[str] | None = "d1f5b9c3e7a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Parâmetros novos: coluna, tipo, valor inicial
PARAMETROS = [
    ("ssgc_nome", sa.String(200), "Laercio Paulino Simões"), ("ssgc_cpf", sa.String(20), "822.684.878-49"),
    ("secretario_nome", sa.String(200), "Rafael Antonio Cren Benini"), ("secretario_cpf", sa.String(20), "223.011.918-42"),
    ("autoridade_competente_nome", sa.String(200), "Laercio Paulino Simões"), ("autoridade_competente_cargo", sa.String(200), "Subsecretário de Gestão Corporativa"),
    ("pncp_dias_uteis_licitacao", sa.Integer(), 20), ("pncp_dias_uteis_direta", sa.Integer(), 10), ("aviso_pncp_dias_uteis", sa.Integer(), 5),
    ("parecer_referencial_validade_dias", sa.Integer(), 365), ("parecer_referencial_vigencia_ate", sa.Date(), date(2027, 2, 9)),
]


def upgrade() -> None:
    op.add_column("contratos", sa.Column("modalidade_contratacao", sa.String(length=20), nullable=False, server_default=""))
    op.add_column("contratos", sa.Column("exige_garantia", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("contratos", sa.Column("garantia_modalidade", sa.String(length=30), nullable=False, server_default=""))
    op.add_column("contratos", sa.Column("garantia_percentual", sa.Numeric(7, 4), nullable=True))
    op.add_column("contratos", sa.Column("garantia_valor", sa.Numeric(18, 2), nullable=True))
    op.add_column("contratos", sa.Column("garantia_emissor", sa.String(length=250), nullable=False, server_default=""))
    op.add_column("contratos", sa.Column("garantia_cnpj_emissor", sa.String(length=14), nullable=False, server_default=""))
    op.add_column("contratos", sa.Column("garantia_apolice", sa.String(length=100), nullable=False, server_default=""))
    op.add_column("contratos_empresas_prepostos", sa.Column("representante_legal", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Parâmetros: a linha única já existe; a coluna nova nasce com o valor inicial
    for nome, tipo, valor in PARAMETROS:
        op.add_column("contratos_parametros", sa.Column(nome, tipo, nullable=False, server_default=sa.text(f"'{valor}'") if isinstance(valor, (str, date)) else str(valor)))


def downgrade() -> None:
    for nome, _, _ in reversed(PARAMETROS):
        op.drop_column("contratos_parametros", nome)
    op.drop_column("contratos_empresas_prepostos", "representante_legal")
    for coluna in ("garantia_apolice", "garantia_cnpj_emissor", "garantia_emissor", "garantia_valor", "garantia_percentual", "garantia_modalidade", "exige_garantia", "modalidade_contratacao"):
        op.drop_column("contratos", coluna)
