# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas da ficha de pré-cadastro do RH (dados pessoais, formações e experiências).

"""rh: pré-cadastro (ficha, formações e experiências)

Revision ID: a8d4f0b6c2e5
Revises: f7c3e9a5b2d4
Create Date: 2026-10-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a8d4f0b6c2e5"
down_revision: str | Sequence[str] | None = "f7c3e9a5b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _texto(nome: str, tamanho: int) -> sa.Column:
    return sa.Column(nome, sa.String(tamanho), nullable=False, server_default="")


def upgrade() -> None:
    op.create_table(
        "rh_pre_cadastros",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="rascunho"),
        sa.Column("login_proposto", sa.String(60)),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("vinculado_em", sa.DateTime(timezone=True)),
        _texto("nome_completo", 200), _texto("nome_social", 200),
        sa.Column("data_nascimento", sa.Date()),
        _texto("sexo", 20), _texto("estado_civil", 30), _texto("nacionalidade", 60), _texto("naturalidade_cidade", 100), _texto("naturalidade_uf", 2),
        _texto("nome_mae", 200), _texto("nome_pai", 200),
        _texto("cpf", 11), _texto("rg_numero", 30), _texto("rg_orgao", 30), _texto("rg_uf", 2),
        sa.Column("rg_emissao", sa.Date()),
        _texto("cin", 30), _texto("pis_pasep", 11), _texto("titulo_numero", 20), _texto("titulo_zona", 5), _texto("titulo_secao", 5),
        _texto("ctps_numero", 20), _texto("ctps_serie", 10), _texto("ctps_uf", 2), _texto("cnh", 20),
        _texto("email_pessoal", 200), _texto("telefone", 30), _texto("celular", 30),
        _texto("emergencia_nome", 200), _texto("emergencia_parentesco", 60), _texto("emergencia_telefone", 30),
        _texto("cep", 8), _texto("logradouro", 200), _texto("numero", 20), _texto("complemento", 100), _texto("bairro", 100), _texto("cidade", 100), _texto("uf", 2),
        _texto("vinculo_tipo", 60), _texto("orgao_origem", 200), _texto("cargo_origem", 200), _texto("rs_pv", 30),
        sa.Column("inicio_previsto", sa.Date()),
        sa.Column("cargo_id", sa.Integer(), sa.ForeignKey("rh_cargos.id", ondelete="SET NULL")),
        sa.Column("observacoes", sa.Text(), nullable=False, server_default=""),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rh_pre_cadastros_status", "rh_pre_cadastros", ["status"])
    op.create_index("ix_rh_pre_cadastros_usuario_id", "rh_pre_cadastros", ["usuario_id"])
    op.create_index("ix_rh_pre_cadastros_cargo_id", "rh_pre_cadastros", ["cargo_id"])
    op.create_index("ux_rh_pre_cadastros_login", "rh_pre_cadastros", [sa.text("lower(login_proposto)")], unique=True,
                    postgresql_where=sa.text("status <> 'cancelado'"), sqlite_where=sa.text("status <> 'cancelado'"))

    op.create_table(
        "rh_ficha_formacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pre_cadastro_id", sa.Integer(), sa.ForeignKey("rh_pre_cadastros.id", ondelete="CASCADE"), nullable=False),
        _texto("nivel", 60), _texto("curso", 200), _texto("instituicao", 200),
        sa.Column("ano_conclusao", sa.Integer()),
        sa.Column("em_andamento", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_rh_ficha_formacoes_pre_cadastro_id", "rh_ficha_formacoes", ["pre_cadastro_id"])

    op.create_table(
        "rh_ficha_experiencias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pre_cadastro_id", sa.Integer(), sa.ForeignKey("rh_pre_cadastros.id", ondelete="CASCADE"), nullable=False),
        _texto("empresa", 200), _texto("cargo", 200),
        sa.Column("inicio", sa.Date()),
        sa.Column("fim", sa.Date()),
        sa.Column("descricao", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_rh_ficha_experiencias_pre_cadastro_id", "rh_ficha_experiencias", ["pre_cadastro_id"])


def downgrade() -> None:
    op.drop_table("rh_ficha_experiencias")
    op.drop_table("rh_ficha_formacoes")
    op.drop_table("rh_pre_cadastros")
