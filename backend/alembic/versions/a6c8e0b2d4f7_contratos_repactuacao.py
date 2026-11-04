# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a repactuação do contrato pela CCT (linhas, vínculos com os itens, fotografia dos preços, memória,
# checklist) e ligar a ela a competência de diferença e o crédito do retroativo.

"""contratos: repactuação pela CCT

- `contratos_repactuacoes` (um rascunho por contrato), `_linhas`, `_vinculos` (linha × item do contrato), `_itens` (fotografia do preço),
  `_memorias` e `_documentos` (checklist);
- `contratos_competencias.repactuacao_id` e o tipo `diferenca_repactuacao`;
- `contratos_abatimentos_reajuste`: `reajuste_id` passa a aceitar vazio e ganha `repactuacao_id` (crédito de uma repactuação);
- `contratos_modelos.tipo` aceita `checklist_repactuacao`.

Revision ID: a6c8e0b2d4f7
Revises: f4b6d8e0a2c3
Create Date: 2026-11-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a6c8e0b2d4f7"
down_revision: str | Sequence[str] | None = "f4b6d8e0a2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPOS_COMPETENCIA = "'regular', 'diferenca_reajuste', 'diferenca_repactuacao', 'adicional'"
TIPOS_COMPETENCIA_ANTES = "'regular', 'diferenca_reajuste', 'adicional'"
TIPOS_MODELO = "'checklist', 'formulario', 'portaria', 'despacho', 'email_cadin', 'email_ob', 'prorrogacao', 'checklist_prorrogacao', 'checklist_repactuacao'"
TIPOS_MODELO_ANTES = "'checklist', 'formulario', 'portaria', 'despacho', 'email_cadin', 'email_ob', 'prorrogacao', 'checklist_prorrogacao'"


def _anexo(nome: str, nulo: bool = True) -> sa.Column:
    return sa.Column(nome, sa.Uuid, sa.ForeignKey("anexos.id", ondelete="RESTRICT"), nullable=nulo)


def upgrade() -> None:
    """Tabelas novas e os tipos novos (nada muda nos registros existentes)."""
    op.create_table(
        "contratos_repactuacoes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("contrato_id", sa.Uuid, sa.ForeignKey("contratos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("situacao", sa.String(20), nullable=False),
        sa.Column("data_base_cct", sa.Date, nullable=False),
        sa.Column("mes_referencia", sa.Date, nullable=False),
        sa.Column("data_efeito", sa.Date, nullable=False),
        sa.Column("cadastro_concluido_em", sa.DateTime(timezone=True)),
        sa.Column("calculo_mes_quebrado", sa.String(10)),
        sa.Column("base_atual", sa.Numeric(18, 2), nullable=False),
        sa.Column("base_repactuada", sa.Numeric(18, 2), nullable=False),
        sa.Column("diferenca_retroativa", sa.Numeric(18, 2)),
        _anexo("cct_anexo_id", nulo=False), _anexo("consolidado_anexo_id"), _anexo("apostilamento_anexo_id"),
        sa.Column("criado_por_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("concluido_em", sa.DateTime(timezone=True)),
        sa.Column("cancelado_em", sa.DateTime(timezone=True)),
        sa.CheckConstraint("situacao IN ('rascunho', 'concluido', 'cancelado')", name="ck_contratos_repactuacoes_situacao"),
    )
    op.create_index("ux_contratos_repactuacoes_rascunho", "contratos_repactuacoes", ["contrato_id"], unique=True,
                    postgresql_where=sa.text("situacao = 'rascunho'"), sqlite_where=sa.text("situacao = 'rascunho'"))
    op.create_table(
        "contratos_repactuacoes_linhas",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("repactuacao_id", sa.Uuid, sa.ForeignKey("contratos_repactuacoes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ordem", sa.Integer, nullable=False),
        sa.Column("descricao", sa.String(500), nullable=False),
        sa.Column("valor_vigente", sa.Numeric(18, 4), nullable=False),
        sa.Column("valor_repactuado", sa.Numeric(18, 4), nullable=False),
    )
    op.create_table(
        "contratos_repactuacoes_vinculos",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("linha_id", sa.Uuid, sa.ForeignKey("contratos_repactuacoes_linhas.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("item_id", sa.Uuid, sa.ForeignKey("contratos_itens.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.UniqueConstraint("linha_id", "item_id"),
    )
    op.create_table(
        "contratos_repactuacoes_itens",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("repactuacao_id", sa.Uuid, sa.ForeignKey("contratos_repactuacoes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("item_id", sa.Uuid, sa.ForeignKey("contratos_itens.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ordem", sa.Integer, nullable=False),
        sa.Column("descricao", sa.String(1000), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("quantidade_mensal", sa.Numeric(18, 4), nullable=False),
        sa.Column("valor_unitario_atual", sa.Numeric(18, 4), nullable=False),
        sa.Column("valor_unitario_repactuado", sa.Numeric(18, 4), nullable=False),
        sa.UniqueConstraint("repactuacao_id", "item_id"),
    )
    op.create_table(
        "contratos_repactuacoes_memorias",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("repactuacao_id", sa.Uuid, sa.ForeignKey("contratos_repactuacoes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("versao", sa.Integer, nullable=False),
        _anexo("pdf_anexo_id", nulo=False), _anexo("xlsx_anexo_id", nulo=False),
        sa.Column("hash_origem", sa.String(64), nullable=False),
        sa.Column("criado_por_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("repactuacao_id", "versao"),
    )
    op.create_table(
        "contratos_repactuacoes_documentos",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("repactuacao_id", sa.Uuid, sa.ForeignKey("contratos_repactuacoes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ordem", sa.Integer, nullable=False),
        sa.Column("nome", sa.String(500), nullable=False),
        sa.Column("observacao", sa.String(1000), nullable=False),
        sa.Column("obrigatorio", sa.Boolean, nullable=False),
        _anexo("anexo_id"),
        sa.Column("enviado_em", sa.DateTime(timezone=True)),
        sa.Column("enviado_por_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("incluido_no_processo", sa.Boolean, nullable=False),
        sa.Column("incluido_por_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("incluido_em", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("repactuacao_id", "ordem"),
    )
    with op.batch_alter_table("contratos_competencias") as tabela:
        tabela.add_column(sa.Column("repactuacao_id", sa.Uuid, sa.ForeignKey("contratos_repactuacoes.id", ondelete="SET NULL",
                                                                              name="fk_contratos_competencias_repactuacao"), nullable=True))
        tabela.create_index("ix_contratos_competencias_repactuacao_id", ["repactuacao_id"])
        tabela.drop_constraint("ck_contratos_competencias_tipo", type_="check")
        tabela.create_check_constraint("ck_contratos_competencias_tipo", f"tipo IN ({TIPOS_COMPETENCIA})")
    with op.batch_alter_table("contratos_abatimentos_reajuste") as tabela:
        tabela.alter_column("reajuste_id", existing_type=sa.Uuid, nullable=True)
        tabela.add_column(sa.Column("repactuacao_id", sa.Uuid, sa.ForeignKey("contratos_repactuacoes.id", ondelete="CASCADE",
                                                                              name="fk_contratos_abatimentos_repactuacao"), nullable=True))
        tabela.create_index("ix_contratos_abatimentos_reajuste_repactuacao_id", ["repactuacao_id"])
    with op.batch_alter_table("contratos_modelos") as tabela:
        tabela.drop_constraint("ck_contratos_modelos_tipo", type_="check")
        tabela.create_check_constraint("ck_contratos_modelos_tipo", f"tipo IN ({TIPOS_MODELO})")


def downgrade() -> None:
    """Desfaz tudo; créditos e competências de diferença de repactuação são apagados."""
    op.execute("DELETE FROM contratos_modelos WHERE tipo = 'checklist_repactuacao'")
    with op.batch_alter_table("contratos_modelos") as tabela:
        tabela.drop_constraint("ck_contratos_modelos_tipo", type_="check")
        tabela.create_check_constraint("ck_contratos_modelos_tipo", f"tipo IN ({TIPOS_MODELO_ANTES})")
    op.execute("DELETE FROM contratos_abatimentos_reajuste WHERE repactuacao_id IS NOT NULL")
    with op.batch_alter_table("contratos_abatimentos_reajuste") as tabela:
        tabela.drop_index("ix_contratos_abatimentos_reajuste_repactuacao_id")
        tabela.drop_column("repactuacao_id")
        tabela.alter_column("reajuste_id", existing_type=sa.Uuid, nullable=False)
    op.execute("DELETE FROM contratos_competencias WHERE tipo = 'diferenca_repactuacao'")
    with op.batch_alter_table("contratos_competencias") as tabela:
        tabela.drop_constraint("ck_contratos_competencias_tipo", type_="check")
        tabela.create_check_constraint("ck_contratos_competencias_tipo", f"tipo IN ({TIPOS_COMPETENCIA_ANTES})")
        tabela.drop_index("ix_contratos_competencias_repactuacao_id")
        tabela.drop_column("repactuacao_id")
    for tabela in ("contratos_repactuacoes_documentos", "contratos_repactuacoes_memorias", "contratos_repactuacoes_itens",
                   "contratos_repactuacoes_vinculos", "contratos_repactuacoes_linhas"):
        op.drop_table(tabela)
    op.drop_index("ux_contratos_repactuacoes_rascunho", table_name="contratos_repactuacoes")
    op.drop_table("contratos_repactuacoes")
