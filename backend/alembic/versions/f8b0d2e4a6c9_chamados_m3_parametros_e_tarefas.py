# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas do marco 3 dos Chamados: status e sub-status, recorrentes e o registro das tarefas automáticas.

"""chamados: status e sub-status, recorrentes e execuções das tarefas automáticas (marco 3)

- `chamados_status_apresentacao`: nome exibido e cor de cada status-base;
- `chamados_substatus`: sub-status dentro de um status-base;
- `chamados_recorrentes`: chamado aberto sozinho a cada período;
- `chamados_execucoes`: cada rodada das tarefas automáticas (o vigia e o painel de saúde leem daqui);
- `chamados.substatus_id`, `chamados.recorrente_id` e `chamados.gerado_para` (único por recorrente: rodar duas vezes não duplica).

Revision ID: f8b0d2e4a6c9
Revises: e7a9c1d3f5b8
Create Date: 2026-11-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f8b0d2e4a6c9"
down_revision: str | Sequence[str] | None = "e7a9c1d3f5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGORA = sa.text("CURRENT_TIMESTAMP")
BASES = "'novo', 'em_atendimento', 'pendente', 'em_aprovacao', 'solucionado'"
CORES = "'info', 'alerta', 'atencao', 'perigo', 'sucesso', 'neutro'"


def upgrade() -> None:
    """Cria as tabelas novas e as colunas do chamado."""
    op.create_table(
        "chamados_status_apresentacao",
        sa.Column("status_base", sa.String(14), primary_key=True),
        sa.Column("nome", sa.String(60), nullable=False),
        sa.Column("cor", sa.String(8), nullable=False),
        sa.CheckConstraint(f"status_base IN ({BASES})", name="ck_chamados_status_apresentacao_base"),
        sa.CheckConstraint(f"cor IN ({CORES})", name="ck_chamados_status_apresentacao_cor"),
    )
    op.create_table(
        "chamados_substatus",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("status_base", sa.String(14), nullable=False, index=True),
        sa.Column("nome", sa.String(60), nullable=False),
        sa.Column("cor", sa.String(8), nullable=False),
        sa.Column("ordem", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint(f"status_base IN ({BASES})", name="ck_chamados_substatus_base"),
        sa.CheckConstraint(f"cor IN ({CORES})", name="ck_chamados_substatus_cor"),
    )
    op.create_table(
        "chamados_recorrentes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("categoria_id", sa.Uuid, sa.ForeignKey("chamados_categorias.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("titulo", sa.String(250), nullable=False),
        sa.Column("descricao", sa.Text, nullable=False, server_default=""),
        sa.Column("solicitante_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("periodicidade_quantidade", sa.Integer, nullable=False, server_default="1"),
        sa.Column("periodicidade_unidade", sa.String(6), nullable=False, server_default="dia"),
        sa.Column("antecedencia_min", sa.Integer, nullable=False, server_default="0"),
        sa.Column("so_dias_uteis", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("proxima_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fim_em", sa.DateTime(timezone=True)),
        sa.Column("ultima_geracao_em", sa.DateTime(timezone=True)),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("origem_glpi_id", sa.Integer),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("periodicidade_unidade IN ('dia', 'semana', 'mes')", name="ck_chamados_recorrentes_unidade"),
        sa.CheckConstraint("periodicidade_quantidade > 0", name="ck_chamados_recorrentes_quantidade"),
        sa.CheckConstraint("antecedencia_min >= 0", name="ck_chamados_recorrentes_antecedencia"),
    )
    op.create_index("ix_chamados_recorrentes_proxima", "chamados_recorrentes", ["ativo", "proxima_em"])
    op.create_table(
        "chamados_execucoes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("tarefa", sa.String(30), nullable=False),
        sa.Column("iniciada_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.Column("terminada_em", sa.DateTime(timezone=True)),
        sa.Column("estado", sa.String(8), nullable=False, server_default="rodando"),
        sa.Column("resumo", sa.String(300), nullable=False, server_default=""),
        sa.Column("erro", sa.Text),
        sa.CheckConstraint("estado IN ('rodando', 'ok', 'erro')", name="ck_chamados_execucoes_estado"),
    )
    op.create_index("ix_chamados_execucoes_tarefa", "chamados_execucoes", ["tarefa", "iniciada_em"])
    op.add_column("chamados", sa.Column("substatus_id", sa.Uuid, sa.ForeignKey("chamados_substatus.id", ondelete="SET NULL")))
    op.add_column("chamados", sa.Column("recorrente_id", sa.Uuid, sa.ForeignKey("chamados_recorrentes.id", ondelete="SET NULL")))
    op.add_column("chamados", sa.Column("gerado_para", sa.DateTime(timezone=True)))
    op.create_index("ux_chamados_recorrencia", "chamados", ["recorrente_id", "gerado_para"], unique=True,
                    postgresql_where=sa.text("recorrente_id IS NOT NULL"))


def downgrade() -> None:
    """Remove as colunas do chamado e as tabelas do marco 3."""
    op.drop_index("ux_chamados_recorrencia", table_name="chamados")
    op.drop_column("chamados", "gerado_para")
    op.drop_column("chamados", "recorrente_id")
    op.drop_column("chamados", "substatus_id")
    for tabela in ("chamados_execucoes", "chamados_recorrentes", "chamados_substatus", "chamados_status_apresentacao"):
        op.drop_table(tabela)
