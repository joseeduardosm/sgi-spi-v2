# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas do marco 2 dos Chamados: campos adicionais, valores, em cópia, tarefas e aprovações.

"""chamados: campos adicionais, em cópia, tarefas e aprovações (marco 2)

- `chamados_campos` / `chamados_valores`: campos adicionais por categoria (valem para as subcategorias) e as respostas; o campo marcado
  como dado pessoal aparece mascarado para quem não atende (LGPD);
- `chamados_atores`: pessoas e setores em cópia;
- `chamados_tarefas`: tarefas da equipe dentro do chamado;
- `chamados_validacoes`: aprovação pedida a uma pessoa ou a um setor.

Revision ID: e7a9c1d3f5b8
Revises: d4f6a8c0e2b5
Create Date: 2026-11-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão e a anterior
revision: str = "e7a9c1d3f5b8"
down_revision: str | Sequence[str] | None = "d4f6a8c0e2b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGORA = sa.text("CURRENT_TIMESTAMP")
JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    """Cria as quatro tabelas novas (nenhuma tabela existente muda)."""
    op.create_table(
        "chamados_campos",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("categoria_id", sa.Uuid, sa.ForeignKey("chamados_categorias.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rotulo", sa.String(150), nullable=False),
        sa.Column("ajuda", sa.String(300)),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("obrigatorio", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("dado_pessoal", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("opcoes", JSON),
        sa.Column("condicao", JSON),
        sa.Column("ordem", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("tipo IN ('texto', 'texto_longo', 'numero', 'data', 'lista', 'sim_nao')", name="ck_chamados_campos_tipo"),
    )
    op.create_table(
        "chamados_valores",
        sa.Column("chamado_id", sa.Uuid, sa.ForeignKey("chamados.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("campo_id", sa.Uuid, sa.ForeignKey("chamados_campos.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("valor", sa.Text, nullable=False),
    )
    op.create_table(
        "chamados_atores",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("chamado_id", sa.Uuid, sa.ForeignKey("chamados.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("papel", sa.String(10), nullable=False, server_default="em_copia"),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="CASCADE")),
        sa.Column("setor_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="CASCADE")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("papel IN ('em_copia')", name="ck_chamados_atores_papel"),
        sa.CheckConstraint("(usuario_id IS NULL) <> (setor_id IS NULL)", name="ck_chamados_atores_alvo"),
    )
    op.create_index("ix_chamados_atores_usuario", "chamados_atores", ["usuario_id"])
    op.create_index("ix_chamados_atores_setor", "chamados_atores", ["setor_id"])
    op.create_table(
        "chamados_tarefas",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("chamado_id", sa.Uuid, sa.ForeignKey("chamados.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("autor_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("responsavel_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("estado", sa.String(7), nullable=False, server_default="a_fazer"),
        sa.Column("privada", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("feita_em", sa.DateTime(timezone=True)),
        sa.Column("origem_glpi_id", sa.Integer),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("estado IN ('a_fazer', 'feita')", name="ck_chamados_tarefas_estado"),
    )
    op.create_table(
        "chamados_validacoes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("chamado_id", sa.Uuid, sa.ForeignKey("chamados.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("solicitante_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("alvo_usuario_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("alvo_setor_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(10), nullable=False, server_default="aguardando"),
        sa.Column("pedido", sa.Text, nullable=False, server_default=""),
        sa.Column("resposta", sa.Text, nullable=False, server_default=""),
        sa.Column("respondida_por_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("respondida_em", sa.DateTime(timezone=True)),
        sa.Column("origem_glpi_id", sa.Integer),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("status IN ('aguardando', 'aprovada', 'recusada')", name="ck_chamados_validacoes_status"),
        sa.CheckConstraint("(alvo_usuario_id IS NULL) <> (alvo_setor_id IS NULL)", name="ck_chamados_validacoes_alvo"),
    )
    op.create_index("ix_chamados_validacoes_usuario", "chamados_validacoes", ["alvo_usuario_id", "status"])
    op.create_index("ix_chamados_validacoes_setor", "chamados_validacoes", ["alvo_setor_id", "status"])


def downgrade() -> None:
    """Remove as tabelas do marco 2."""
    for tabela in ("chamados_validacoes", "chamados_tarefas", "chamados_atores", "chamados_valores", "chamados_campos"):
        op.drop_table(tabela)
