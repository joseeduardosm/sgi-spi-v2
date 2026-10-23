# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas da admissão do RH (modelos, checklists e a trilha) e, no usuário, os campos de boas-vindas e de bio.

"""rh: admissão (modelos, checklists, trilha) e boas-vindas/bio do usuário

Revision ID: b9e5a1c7d3f6
Revises: a8d4f0b6c2e5
Create Date: 2026-10-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b9e5a1c7d3f6"
down_revision: str | Sequence[str] | None = "a8d4f0b6c2e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rh_modelos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(40), nullable=False, unique=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("assunto", sa.String(300), nullable=False, server_default=""),
        sa.Column("html", sa.Text(), nullable=False, server_default=""),
        sa.Column("atualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "rh_checklists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "rh_checklist_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("checklist_id", sa.Integer(), sa.ForeignKey("rh_checklists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("descricao", sa.String(300), nullable=False),
        sa.Column("obrigatorio", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_rh_checklist_itens_checklist_id", "rh_checklist_itens", ["checklist_id"])
    op.create_table(
        "rh_checklist_tipos",
        sa.Column("checklist_id", sa.Integer(), sa.ForeignKey("rh_checklists.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tipo_id", sa.Integer(), sa.ForeignKey("rh_tipos_cargo.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "rh_admissoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pre_cadastro_id", sa.Integer(), sa.ForeignKey("rh_pre_cadastros.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cargo_id", sa.Integer(), sa.ForeignKey("rh_cargos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="andamento"),
        sa.Column("solicitacoes", sa.JSON()),
        sa.Column("chamado_glpi_id", sa.Integer()),
        sa.Column("chamado_url", sa.String(500)),
        sa.Column("chamado_em", sa.DateTime(timezone=True)),
        sa.Column("documentos_concluidos_em", sa.DateTime(timezone=True)),
        sa.Column("resolucao_html", sa.Text()),
        sa.Column("resolucao_gerada_em", sa.DateTime(timezone=True)),
        sa.Column("numero_protocolo_id", sa.Uuid(), sa.ForeignKey("protocolo_numeros.id", ondelete="SET NULL")),
        sa.Column("protocolo_em", sa.DateTime(timezone=True)),
        sa.Column("publicado_em", sa.Date()),
        sa.Column("publicacao_registrada_em", sa.DateTime(timezone=True)),
        sa.Column("email_enviado_em", sa.DateTime(timezone=True)),
        sa.Column("posse_em", sa.Date()),
        sa.Column("termo_html", sa.Text()),
        sa.Column("concluida_em", sa.DateTime(timezone=True)),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("pre_cadastro_id", name="ux_rh_admissao_ficha"),
    )
    op.create_index("ix_rh_admissoes_pre_cadastro_id", "rh_admissoes", ["pre_cadastro_id"])
    op.create_index("ix_rh_admissoes_cargo_id", "rh_admissoes", ["cargo_id"])
    op.create_index("ix_rh_admissoes_status", "rh_admissoes", ["status"])
    op.create_table(
        "rh_admissao_documentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admissao_id", sa.Integer(), sa.ForeignKey("rh_admissoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("descricao", sa.String(300), nullable=False),
        sa.Column("obrigatorio", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enviado_em", sa.Date()),
        sa.Column("enviado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("enviado_por_nome", sa.String(200), nullable=False, server_default=""),
        sa.Column("registrado_em", sa.DateTime(timezone=True)),
        sa.Column("comprovante_anexo_id", sa.Uuid(), sa.ForeignKey("anexos.id", ondelete="SET NULL")),
        sa.Column("observacao", sa.String(500), nullable=False, server_default=""),
    )
    op.create_index("ix_rh_admissao_documentos_admissao_id", "rh_admissao_documentos", ["admissao_id"])

    # Boas-vindas (primeiro acesso) e bio. Quem já usa o sistema não vê as boas-vindas: nasce marcado como já visto.
    op.add_column("usuarios", sa.Column("boas_vindas_em", sa.DateTime(timezone=True)))
    op.add_column("usuarios", sa.Column("boas_vindas_email_em", sa.DateTime(timezone=True)))
    op.add_column("usuarios", sa.Column("bio_texto", sa.Text(), nullable=False, server_default=""))
    op.add_column("usuarios", sa.Column("bio_visivel", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(sa.text("UPDATE usuarios SET boas_vindas_em = CURRENT_TIMESTAMP, boas_vindas_email_em = CURRENT_TIMESTAMP"))
    # Ficha de quem já tem conta (legados): o próprio usuário preenche e o RH valida
    op.add_column("rh_pre_cadastros", sa.Column("validado_em", sa.DateTime(timezone=True)))
    op.add_column("rh_pre_cadastros", sa.Column("validado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")))
    op.add_column("rh_pre_cadastros", sa.Column("enviada_em", sa.DateTime(timezone=True)))


def downgrade() -> None:
    with op.batch_alter_table("rh_pre_cadastros") as lote:
        lote.drop_column("enviada_em")
        lote.drop_column("validado_por_id")
        lote.drop_column("validado_em")
    with op.batch_alter_table("usuarios") as lote:
        lote.drop_column("bio_visivel")
        lote.drop_column("bio_texto")
        lote.drop_column("boas_vindas_email_em")
        lote.drop_column("boas_vindas_em")
    op.drop_table("rh_admissao_documentos")
    op.drop_table("rh_admissoes")
    op.drop_table("rh_checklist_tipos")
    op.drop_table("rh_checklist_itens")
    op.drop_table("rh_checklists")
    op.drop_table("rh_modelos")
