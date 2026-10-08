# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a configuração da integração com o BookStack e o recurso de ACL "manuais" (aberto a todos).
"""integração com o BookStack: configuração e recurso de ACL `manuais`

O recurso `manuais` nasce **sem regras**: na ACL, recurso sem regras fica aberto a todo usuário autenticado, que é o pedido (todos leem os
manuais). O SuperRoot pode restringir depois na tela de Controle de acesso.

Revision ID: d7a1c5e9b3f2
Revises: c6e0a4b8d2f1
Create Date: 2026-10-06 13:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d7a1c5e9b3f2"
down_revision: str | Sequence[str] | None = "c6e0a4b8d2f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "manuais"


def upgrade() -> None:
    """Cria a tabela (com a linha única de configuração, desligada) e o recurso de ACL."""
    op.create_table(
        "integracao_bookstack",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("url_base", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("token_id_cifrado", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("token_segredo_cifrado", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_por", sa.String(length=150), nullable=False, server_default=""),
    )
    op.execute(sa.text("INSERT INTO integracao_bookstack (id, url_base) VALUES (1, 'https://instrucoes.spi.sp.gov.br')"))
    conexao = op.get_bind()
    # Idempotente: se o recurso já foi criado à mão na tela de ACL, não duplica
    if conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :slug"), {"slug": SLUG}) is None:
        conexao.execute(
            sa.text(
                "INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES (:nome, :slug, :descricao, '/manuais', true, :agora, :agora)"
            ),
            {"nome": "Manuais", "slug": SLUG, "agora": datetime.now(UTC),
             "descricao": "Manuais do BookStack lidos dentro do portal. Sem regras: todo usuário autenticado."},
        )


def downgrade() -> None:
    """Remove a tabela e o recurso de ACL."""
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :slug").bindparams(slug=SLUG))
    op.drop_table("integracao_bookstack")
