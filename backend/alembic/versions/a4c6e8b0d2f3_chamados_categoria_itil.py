# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a Categoria ITIL dos Chamados (classificação técnica), separada da categoria de assunto.

"""chamados: categoria ITIL (árvore própria), ITIL padrão no assunto e ITIL do chamado

- `chamados_categorias_itil`: árvore como a dos assuntos (nome único por nível, caminho, ordem, ativa, origem do GLPI);
- `chamados_categorias.categoria_itil_id`: a ITIL que o chamado recebe ao abrir no assunto (nula = herda da mãe ou fica pendente);
- `chamados.categoria_itil_id`: a classificação do chamado (nula = pendente).

Revision ID: a4c6e8b0d2f3
Revises: f2b4d6e8a0c1
Create Date: 2026-11-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a4c6e8b0d2f3"
down_revision: str | Sequence[str] | None = "f2b4d6e8a0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria a árvore ITIL e as duas colunas que apontam para ela."""
    op.create_table(
        "chamados_categorias_itil",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("pai_id", sa.Uuid, sa.ForeignKey("chamados_categorias_itil.id", ondelete="RESTRICT"), index=True),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("caminho", sa.String(800), nullable=False),
        sa.Column("nivel", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("ordem", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ativa", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("origem_glpi_id", sa.Integer),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ux_chamados_categorias_itil_pai_nome", "chamados_categorias_itil",
                    [sa.text("coalesce(CAST(pai_id AS VARCHAR), '')"), sa.text("lower(nome)")], unique=True)
    op.create_index("ux_chamados_categorias_itil_glpi", "chamados_categorias_itil", ["origem_glpi_id"], unique=True,
                    postgresql_where=sa.text("origem_glpi_id IS NOT NULL"))
    with op.batch_alter_table("chamados_categorias") as tabela:
        tabela.add_column(sa.Column("categoria_itil_id", sa.Uuid, sa.ForeignKey("chamados_categorias_itil.id", ondelete="SET NULL",
                                                                                    name="fk_chamados_categorias_itil_padrao")))
    with op.batch_alter_table("chamados") as tabela:
        tabela.add_column(sa.Column("categoria_itil_id", sa.Uuid, sa.ForeignKey("chamados_categorias_itil.id", ondelete="SET NULL",
                                                                                    name="fk_chamados_categoria_itil")))
        tabela.create_index("ix_chamados_categoria_itil_id", ["categoria_itil_id"])


def downgrade() -> None:
    with op.batch_alter_table("chamados") as tabela:
        tabela.drop_index("ix_chamados_categoria_itil_id")
        tabela.drop_column("categoria_itil_id")
    with op.batch_alter_table("chamados_categorias") as tabela:
        tabela.drop_column("categoria_itil_id")
    op.drop_index("ux_chamados_categorias_itil_glpi", "chamados_categorias_itil")
    op.drop_index("ux_chamados_categorias_itil_pai_nome", "chamados_categorias_itil")
    op.drop_table("chamados_categorias_itil")
