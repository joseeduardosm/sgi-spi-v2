# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas de cargos, ocupações e histórico do RH e as colunas de sigla e tipo de unidade dos setores.

"""rh: cargos (vagas por setor), ocupações, histórico da vida funcional e sigla/tipo dos setores

Revision ID: e6b2d8f4a1c3
Revises: d5a1c7e3b9f2
Create Date: 2026-10-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão e a anterior
revision: str = "e6b2d8f4a1c3"
down_revision: str | Sequence[str] | None = "d5a1c7e3b9f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# JSON no SQLite (testes) e JSONB no PostgreSQL, como o `TipoJson` dos modelos
JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column("setores", sa.Column("sigla", sa.String(30), nullable=True))
    op.add_column("setores", sa.Column("tipo_unidade", sa.String(30), nullable=True))

    tipos = op.create_table(
        "rh_tipos_cargo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(20), nullable=False, unique=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.bulk_insert(tipos, [
        {"codigo": "CCESP", "nome": "Cargo em comissão (CCESP)", "ordem": 1, "ativo": True},
        {"codigo": "FCESP", "nome": "Função de confiança (FCESP)", "ordem": 2, "ativo": True},
        {"codigo": "OUTRO", "nome": "Outros", "ordem": 9, "ativo": True},
    ])

    op.create_table(
        "rh_cargos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("setor_id", sa.Integer(), sa.ForeignKey("setores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tipo_id", sa.Integer(), sa.ForeignKey("rh_tipos_cargo.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("grupo", sa.SmallInteger(), nullable=True),
        sa.Column("nivel", sa.SmallInteger(), nullable=True),
        sa.Column("denominacao", sa.String(200), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rh_cargos_setor", "rh_cargos", ["setor_id"])

    op.create_table(
        "rh_ocupacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cargo_id", sa.Integer(), sa.ForeignKey("rh_cargos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inicio", sa.Date(), nullable=False),
        sa.Column("fim", sa.Date(), nullable=True),
        sa.Column("ato", sa.String(200), nullable=False, server_default=""),
        sa.Column("motivo_fim", sa.String(20), nullable=True),
        sa.Column("ato_fim", sa.String(200), nullable=False, server_default=""),
        sa.Column("registrado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("registrado_por_nome", sa.String(200), nullable=False, server_default=""),
        sa.Column("registrado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rh_ocupacoes_usuario", "rh_ocupacoes", ["usuario_id"])
    op.create_index("ux_rh_ocupacao_cargo_vigente", "rh_ocupacoes", ["cargo_id"], unique=True, postgresql_where=sa.text("fim IS NULL"))
    op.create_index("ux_rh_ocupacao_usuario_vigente", "rh_ocupacoes", ["usuario_id"], unique=True, postgresql_where=sa.text("fim IS NULL"))

    op.create_table(
        "rh_historico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("titulo", sa.String(300), nullable=False),
        sa.Column("detalhe", sa.Text(), nullable=False, server_default=""),
        sa.Column("ocorrido_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("autor_nome", sa.String(200), nullable=False, server_default="Sistema"),
        sa.Column("origem_tipo", sa.String(30), nullable=True),
        sa.Column("origem_id", sa.String(64), nullable=True),
        sa.Column("sigiloso", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dados", JSON, nullable=True),
    )
    op.create_index("ix_rh_historico_usuario", "rh_historico", ["usuario_id", "ocorrido_em"])
    op.create_index("ux_rh_historico_origem", "rh_historico", ["origem_tipo", "origem_id"], unique=True, postgresql_where=sa.text("origem_tipo IS NOT NULL"))


def downgrade() -> None:
    op.drop_table("rh_historico")
    op.drop_table("rh_ocupacoes")
    op.drop_table("rh_cargos")
    op.drop_table("rh_tipos_cargo")
    op.drop_column("setores", "tipo_unidade")
    op.drop_column("setores", "sigla")
