# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas da integração com o GLPI e o recurso de ACL "abrir-chamado" (aberto a todos).
"""integração com o GLPI: configuração, chamados abertos e recurso de ACL `abrir-chamado`

O recurso `abrir-chamado` nasce **sem regras**: na ACL, recurso sem regras fica aberto a todo usuário autenticado,
que é o pedido (todo usuário abre chamado). O SuperRoot pode restringir depois na tela de Controle de acesso.

Revision ID: d1f4b8a2e6c9
Revises: c9e3a7f1b5d8
Create Date: 2026-10-05 14:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d1f4b8a2e6c9"
down_revision: str | Sequence[str] | None = "c9e3a7f1b5d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "abrir-chamado"


def upgrade() -> None:
    """Cria as duas tabelas (com a linha única de configuração, desligada) e o recurso de ACL."""
    op.create_table(
        "integracao_glpi",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("url_base", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("app_token_cifrado", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("user_token_cifrado", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("tipo_padrao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("urgencia_padrao", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("origem_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_por", sa.String(length=150), nullable=False, server_default=""),
    )
    op.execute(sa.text("INSERT INTO integracao_glpi (id, url_base) VALUES (1, 'https://chamados.spi.sp.gov.br')"))
    op.create_table(
        "chamados_glpi",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("glpi_id", sa.Integer(), nullable=False),
        sa.Column("assunto", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=400), nullable=False),
        sa.Column("aberto_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chamados_glpi_usuario_id", "chamados_glpi", ["usuario_id"])
    op.create_index("ix_chamados_glpi_aberto_em", "chamados_glpi", ["aberto_em"])
    conexao = op.get_bind()
    # Idempotente: se o recurso já foi criado à mão na tela de ACL, não duplica
    if conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :slug"), {"slug": SLUG}) is None:
        agora = datetime.now(UTC)
        conexao.execute(
            sa.text(
                "INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES (:nome, :slug, :descricao, '/', true, :agora, :agora)"
            ),
            {"nome": "Abrir chamado", "slug": SLUG, "agora": agora,
             "descricao": "Item \"Abrir Chamado\" da barra lateral (abre o chamado no GLPI). Sem regras: todo usuário autenticado."},
        )


def downgrade() -> None:
    """Remove as tabelas e o recurso de ACL."""
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :slug").bindparams(slug=SLUG))
    op.drop_index("ix_chamados_glpi_aberto_em", table_name="chamados_glpi")
    op.drop_index("ix_chamados_glpi_usuario_id", table_name="chamados_glpi")
    op.drop_table("chamados_glpi")
    op.drop_table("integracao_glpi")
