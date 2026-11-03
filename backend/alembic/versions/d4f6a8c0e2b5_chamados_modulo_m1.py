# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas do módulo Chamados (marco 1: abrir, atender e solucionar) e cadastrar o recurso na ACL.

"""chamados: módulo Chamados (marco 1) e recurso `chamados` na ACL

Cria as tabelas do primeiro marco do módulo que substitui a Assistência do GLPI: parâmetros, ajustes dos setores de atendimento,
expedientes (os feriados vêm de `rh_feriados`), SLAs, categorias em árvore, o chamado e a linha do tempo (acompanhamentos, soluções
e anexos). O recurso `chamados` nasce **sem regras**: diferente dos outros módulos, ele fica **fechado** (só o SuperRoot) até alguém
criar regras ou perfis, porque o GLPI continua em uso até a virada.

Revision ID: d4f6a8c0e2b5
Revises: c3e5a7b9d2f4
Create Date: 2026-11-01
"""
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d4f6a8c0e2b5"
down_revision: str | Sequence[str] | None = "c3e5a7b9d2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "chamados"
# Colunas de data comuns
AGORA = sa.text("CURRENT_TIMESTAMP")


def _datas() -> list[sa.Column]:
    """criado_em e atualizado_em, como nos outros módulos."""
    return [
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
    ]


def upgrade() -> None:
    """Cria as tabelas na ordem das chaves estrangeiras e cadastra o recurso da ACL."""
    op.create_table(
        "chamados_parametros",
        sa.Column("chave", sa.String(60), primary_key=True),
        sa.Column("valor", sa.String(400), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
    )
    op.create_table(
        "chamados_setores_atendimento",
        sa.Column("setor_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("ve_todos", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("area_painel_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="RESTRICT")),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
    )
    op.create_table(
        "chamados_expedientes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False, unique=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("origem_glpi_id", sa.Integer),
        *_datas(),
    )
    op.create_table(
        "chamados_expediente_faixas",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("expediente_id", sa.Uuid, sa.ForeignKey("chamados_expedientes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("dia_semana", sa.SmallInteger, nullable=False),
        sa.Column("inicio", sa.Time, nullable=False),
        sa.Column("fim", sa.Time, nullable=False),
        sa.CheckConstraint("dia_semana BETWEEN 0 AND 6", name="ck_chamados_faixa_dia"),
        sa.CheckConstraint("fim > inicio", name="ck_chamados_faixa_ordem"),
    )
    op.create_table(
        "chamados_slas",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("tipo", sa.String(3), nullable=False),
        sa.Column("tempo", sa.Integer, nullable=False),
        sa.Column("unidade", sa.String(6), nullable=False),
        sa.Column("expediente_id", sa.Uuid, sa.ForeignKey("chamados_expedientes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("origem_glpi_id", sa.Integer),
        *_datas(),
        sa.CheckConstraint("tipo IN ('tto', 'ttr')", name="ck_chamados_slas_tipo"),
        sa.CheckConstraint("unidade IN ('minuto', 'hora', 'dia')", name="ck_chamados_slas_unidade"),
        sa.CheckConstraint("tempo > 0", name="ck_chamados_slas_tempo"),
    )
    op.create_table(
        "chamados_categorias",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("pai_id", sa.Uuid, sa.ForeignKey("chamados_categorias.id", ondelete="RESTRICT"), index=True),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("caminho", sa.String(800), nullable=False),
        sa.Column("nivel", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("ordem", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ativa", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("visivel_solicitante", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("permite_incidente", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("permite_requisicao", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("setor_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="RESTRICT"), index=True),
        sa.Column("responsavel_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("sla_tto_id", sa.Uuid, sa.ForeignKey("chamados_slas.id", ondelete="RESTRICT")),
        sa.Column("sla_ttr_id", sa.Uuid, sa.ForeignKey("chamados_slas.id", ondelete="RESTRICT")),
        sa.Column("prioridade_padrao", sa.String(7)),
        sa.Column("perguntar_impedindo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sigilosa", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("origem_glpi_id", sa.Integer),
        *_datas(),
        sa.CheckConstraint("prioridade_padrao IS NULL OR prioridade_padrao IN ('baixa', 'normal', 'alta', 'urgente')", name="ck_chamados_categorias_prioridade"),
    )
    op.create_index("ux_chamados_categorias_pai_nome", "chamados_categorias",
                    [sa.text("coalesce(CAST(pai_id AS VARCHAR), '')"), sa.text("lower(nome)")], unique=True)
    op.create_index("ux_chamados_categorias_glpi", "chamados_categorias", ["origem_glpi_id"], unique=True,
                    postgresql_where=sa.text("origem_glpi_id IS NOT NULL"))
    op.create_table(
        "chamados",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("numero", sa.Integer, nullable=False, unique=True),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("titulo", sa.String(250), nullable=False),
        sa.Column("descricao", sa.Text, nullable=False),
        sa.Column("status_base", sa.String(14), nullable=False, index=True),
        sa.Column("prioridade", sa.String(7), nullable=False),
        sa.Column("prioridade_origem", sa.String(11), nullable=False),
        sa.Column("impedindo_trabalho", sa.Boolean),
        sa.Column("categoria_id", sa.Uuid, sa.ForeignKey("chamados_categorias.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("setor_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("setor_nome", sa.String(150), nullable=False),
        sa.Column("responsavel_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("solicitante_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("setor_solicitante_id", sa.Integer, sa.ForeignKey("setores.id", ondelete="SET NULL")),
        sa.Column("solicitante_externo", sa.String(254)),
        sa.Column("aberto_por_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("localizacao_id", sa.Uuid, sa.ForeignKey("patrimonio_localizacoes.id", ondelete="SET NULL")),
        sa.Column("sla_tto_id", sa.Uuid, sa.ForeignKey("chamados_slas.id", ondelete="SET NULL")),
        sa.Column("sla_ttr_id", sa.Uuid, sa.ForeignKey("chamados_slas.id", ondelete="SET NULL")),
        sa.Column("prazo_tto", sa.DateTime(timezone=True)),
        sa.Column("prazo_ttr", sa.DateTime(timezone=True)),
        sa.Column("tomado_em", sa.DateTime(timezone=True)),
        sa.Column("espera_desde", sa.DateTime(timezone=True)),
        sa.Column("espera_minutos_uteis", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tto_estourado_em", sa.DateTime(timezone=True)),
        sa.Column("ttr_estourado_em", sa.DateTime(timezone=True)),
        sa.Column("aberto_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.Column("solucionado_em", sa.DateTime(timezone=True)),
        sa.Column("reabrir_ate", sa.DateTime(timezone=True)),
        sa.Column("reaberturas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("relacionado_id", sa.Uuid, sa.ForeignKey("chamados.id", ondelete="SET NULL")),
        sa.Column("pai_id", sa.Uuid, sa.ForeignKey("chamados.id", ondelete="RESTRICT"), index=True),
        sa.Column("admissao_id", sa.Integer, sa.ForeignKey("rh_admissoes.id", ondelete="SET NULL"), index=True),
        sa.Column("importado", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("origem_glpi_id", sa.Integer),
        sa.Column("versao", sa.Integer, nullable=False, server_default="1"),
        sa.Column("excluido_em", sa.DateTime(timezone=True)),
        *_datas(),
        sa.CheckConstraint("tipo IN ('incidente', 'requisicao')", name="ck_chamados_tipo"),
        sa.CheckConstraint("status_base IN ('novo', 'em_atendimento', 'pendente', 'em_aprovacao', 'solucionado')", name="ck_chamados_status"),
        sa.CheckConstraint("prioridade IN ('baixa', 'normal', 'alta', 'urgente')", name="ck_chamados_prioridade"),
        sa.CheckConstraint("prioridade_origem IN ('categoria', 'solicitante', 'responsavel', 'sla', 'importado')", name="ck_chamados_prioridade_origem"),
        sa.CheckConstraint("solicitante_id IS NOT NULL OR setor_solicitante_id IS NOT NULL OR solicitante_externo IS NOT NULL", name="ck_chamados_solicitante"),
    )
    op.create_index("ux_chamados_glpi", "chamados", ["origem_glpi_id"], unique=True, postgresql_where=sa.text("origem_glpi_id IS NOT NULL"))
    op.create_index("ix_chamados_fila", "chamados", ["setor_id", "status_base", "prioridade"], postgresql_where=sa.text("excluido_em IS NULL"))
    op.create_index("ix_chamados_responsavel", "chamados", ["responsavel_id", "status_base"])
    op.create_index("ix_chamados_solicitante", "chamados", ["solicitante_id", "aberto_em"])
    op.create_table(
        "chamados_acompanhamentos",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("chamado_id", sa.Uuid, sa.ForeignKey("chamados.id", ondelete="CASCADE"), nullable=False),
        sa.Column("autor_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("privado", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("automatico", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("origem_glpi_id", sa.Integer),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
    )
    op.create_index("ix_chamados_acompanhamentos_chamado", "chamados_acompanhamentos", ["chamado_id", "criado_em"])
    op.create_table(
        "chamados_solucoes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("chamado_id", sa.Uuid, sa.ForeignKey("chamados.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("autor_id", sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("status", sa.String(11), nullable=False, server_default="vigente"),
        sa.Column("origem_glpi_id", sa.Integer),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("status IN ('vigente', 'substituida')", name="ck_chamados_solucoes_status"),
    )
    op.create_table(
        "chamados_anexos",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("chamado_id", sa.Uuid, sa.ForeignKey("chamados.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("anexo_id", sa.Uuid, sa.ForeignKey("anexos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("alvo_tipo", sa.String(14), nullable=False, server_default="chamado"),
        sa.Column("alvo_id", sa.Uuid),
        sa.Column("privado", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("origem_glpi_id", sa.Integer),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("alvo_tipo IN ('chamado', 'acompanhamento', 'solucao')", name="ck_chamados_anexos_alvo"),
    )

    # Recurso da ACL (idempotente). Sem regras: o próprio módulo fica fechado, só o SuperRoot entra até alguém liberar.
    conexao = op.get_bind()
    if conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :slug"), {"slug": SLUG}) is None:
        conexao.execute(
            sa.text(
                "INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES (:nome, :slug, :descricao, '/chamados', true, :agora, :agora)"
            ),
            {"nome": "Chamados", "slug": SLUG, "agora": datetime.now(UTC),
             "descricao": "Abrir, atender e administrar chamados. Fechado (só SuperRoot) até haver regras ou perfis: o GLPI segue em uso até a virada."},
        )


def downgrade() -> None:
    """Remove o recurso e as tabelas, na ordem inversa das chaves estrangeiras."""
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :slug").bindparams(slug=SLUG))
    for tabela in ("chamados_anexos", "chamados_solucoes", "chamados_acompanhamentos", "chamados", "chamados_categorias", "chamados_slas",
                   "chamados_expediente_faixas", "chamados_expedientes", "chamados_setores_atendimento", "chamados_parametros"):
        op.drop_table(tabela)
