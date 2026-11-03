# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas do plano de face da rede e o recurso `rede` da ACL (marco 7 dos Chamados).

"""rede: plano de face (modelos de face, equipamentos, portas, VLANs, conexões e pontos) e porta/ponto no chamado

- `rede_*`: ver `app/models/rede.py`;
- `chamados.rede_porta_id` e `chamados.rede_ponto_id`: o chamado aponta a porta ou o ponto do problema;
- recurso `rede` na ACL: fechado (só o SuperRoot) até haver regras, como o dos Chamados.

Revision ID: c5e7a9b1d3f6
Revises: b3d5f7a9c1e4
Create Date: 2026-11-01
"""
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão e a anterior
revision: str = "c5e7a9b1d3f6"
down_revision: str | Sequence[str] | None = "b3d5f7a9c1e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGORA = sa.text("CURRENT_TIMESTAMP")
SLUG = "rede"


def upgrade() -> None:
    """Cria as tabelas, as colunas do chamado e o recurso da ACL."""
    op.create_table(
        "rede_modelos_face",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("nome", sa.String(150), nullable=False, unique=True),
        sa.Column("fabricante", sa.String(120), nullable=False, server_default=""),
        sa.Column("linhas", sa.Integer, nullable=False),
        sa.Column("colunas", sa.Integer, nullable=False),
        sa.Column("numeracao", sa.String(6), nullable=False),
        sa.Column("portas_extras", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("altura_u", sa.Integer, nullable=False, server_default="1"),
        sa.Column("origem_glpi_id", sa.Integer, unique=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("numeracao IN ('coluna', 'linha')", name="ck_rede_modelos_face_numeracao"),
        sa.CheckConstraint("linhas BETWEEN 1 AND 8 AND colunas BETWEEN 1 AND 64", name="ck_rede_modelos_face_grade"),
    )
    op.create_table(
        "rede_equipamentos",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("modelo_face_id", sa.Uuid, sa.ForeignKey("rede_modelos_face.id", ondelete="SET NULL")),
        sa.Column("bem_id", sa.Uuid, sa.ForeignKey("patrimonio_bens.id", ondelete="SET NULL")),
        sa.Column("localizacao_id", sa.Uuid, sa.ForeignKey("patrimonio_localizacoes.id", ondelete="SET NULL"), index=True),
        sa.Column("rack", sa.String(60), nullable=False, server_default=""),
        sa.Column("posicao_u", sa.Integer),
        sa.Column("ip_gerencia", sa.String(45), nullable=False, server_default=""),
        sa.Column("numero_serie", sa.String(120), nullable=False, server_default=""),
        sa.Column("observacao", sa.Text, nullable=False, server_default=""),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("origem_glpi_id", sa.Integer, unique=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("tipo IN ('switch', 'patch_panel', 'roteador', 'outro')", name="ck_rede_equipamentos_tipo"),
    )
    op.create_table(
        "rede_vlans",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("numero", sa.Integer, nullable=False, unique=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("descricao", sa.Text, nullable=False, server_default=""),
        sa.Column("origem_glpi_id", sa.Integer, unique=True),
        sa.CheckConstraint("numero BETWEEN 1 AND 4094", name="ck_rede_vlans_numero"),
    )
    op.create_table(
        "rede_portas",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("equipamento_id", sa.Uuid, sa.ForeignKey("rede_equipamentos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero_logico", sa.Integer, nullable=False),
        sa.Column("nome", sa.String(120), nullable=False, server_default=""),
        sa.Column("descricao", sa.String(250), nullable=False, server_default=""),
        sa.Column("mac", sa.String(17), nullable=False, server_default=""),
        sa.Column("velocidade_mbps", sa.Integer),
        sa.Column("duplex", sa.String(4)),
        sa.Column("status", sa.String(10)),
        sa.Column("modo", sa.String(6), nullable=False, server_default="access"),
        sa.Column("vlan_nativa_id", sa.Uuid, sa.ForeignKey("rede_vlans.id", ondelete="SET NULL")),
        sa.Column("ultima_mudanca", sa.DateTime(timezone=True)),
        sa.Column("erros_entrada", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("erros_saida", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("origem_glpi_id", sa.Integer, unique=True),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.UniqueConstraint("equipamento_id", "numero_logico", name="uq_rede_portas_numero"),
        sa.CheckConstraint("status IS NULL OR status IN ('up', 'down', 'desativada')", name="ck_rede_portas_status"),
        sa.CheckConstraint("modo IN ('access', 'trunk')", name="ck_rede_portas_modo"),
        sa.CheckConstraint("duplex IS NULL OR duplex IN ('full', 'half')", name="ck_rede_portas_duplex"),
    )
    op.create_table(
        "rede_portas_vlans",
        sa.Column("porta_id", sa.Uuid, sa.ForeignKey("rede_portas.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("vlan_id", sa.Uuid, sa.ForeignKey("rede_vlans.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "rede_conexoes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("porta_a_id", sa.Uuid, sa.ForeignKey("rede_portas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("porta_b_id", sa.Uuid, sa.ForeignKey("rede_portas.id", ondelete="CASCADE")),
        sa.Column("bem_id", sa.Uuid, sa.ForeignKey("patrimonio_bens.id", ondelete="SET NULL")),
        sa.Column("descricao", sa.String(250), nullable=False, server_default=""),
        sa.Column("origem_glpi_id", sa.Integer),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
        sa.CheckConstraint("porta_b_id IS NULL OR porta_b_id <> porta_a_id", name="ck_rede_conexoes_diferentes"),
    )
    op.create_index("ux_rede_conexoes_a", "rede_conexoes", ["porta_a_id"], unique=True)
    op.create_index("ux_rede_conexoes_b", "rede_conexoes", ["porta_b_id"], unique=True, postgresql_where=sa.text("porta_b_id IS NOT NULL"))
    op.create_table(
        "rede_pontos",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("codigo", sa.String(40), nullable=False, unique=True),
        sa.Column("localizacao_id", sa.Uuid, sa.ForeignKey("patrimonio_localizacoes.id", ondelete="SET NULL"), index=True),
        sa.Column("porta_id", sa.Uuid, sa.ForeignKey("rede_portas.id", ondelete="SET NULL"), unique=True),
        sa.Column("observacao", sa.Text, nullable=False, server_default=""),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=AGORA),
    )
    op.add_column("chamados", sa.Column("rede_porta_id", sa.Uuid, sa.ForeignKey("rede_portas.id", ondelete="SET NULL")))
    op.add_column("chamados", sa.Column("rede_ponto_id", sa.Uuid, sa.ForeignKey("rede_pontos.id", ondelete="SET NULL")))
    op.create_index("ix_chamados_rede_porta_id", "chamados", ["rede_porta_id"])
    op.create_index("ix_chamados_rede_ponto_id", "chamados", ["rede_ponto_id"])

    # Recurso da ACL (idempotente). Sem regras: fechado, só o SuperRoot entra até alguém liberar (dados de infraestrutura).
    conexao = op.get_bind()
    if conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :slug"), {"slug": SLUG}) is None:
        conexao.execute(
            sa.text(
                "INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES (:nome, :slug, :descricao, '/rede', true, :agora, :agora)"
            ),
            {"nome": "Plano de face (rede)", "slug": SLUG, "agora": datetime.now(UTC),
             "descricao": "Switches, patch panels, portas, VLANs e pontos de rede. Fechado (só SuperRoot) até haver regras ou perfis."},
        )


def downgrade() -> None:
    """Remove o recurso, as colunas do chamado e as tabelas."""
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :slug").bindparams(slug=SLUG))
    op.drop_index("ix_chamados_rede_ponto_id", table_name="chamados")
    op.drop_index("ix_chamados_rede_porta_id", table_name="chamados")
    op.drop_column("chamados", "rede_ponto_id")
    op.drop_column("chamados", "rede_porta_id")
    for tabela in ("rede_pontos", "rede_conexoes", "rede_portas_vlans", "rede_portas", "rede_vlans", "rede_equipamentos", "rede_modelos_face"):
        op.drop_table(tabela)
