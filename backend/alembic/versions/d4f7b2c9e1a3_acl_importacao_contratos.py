# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar o recurso de ACL que libera a importação de contratos por XLSX.
"""acl: recurso `importacao-contratos` (importação de contrato por planilha XLSX)

Na ACL, um recurso sem regras fica aberto a todos os usuários autenticados. Para que o botão
"Importar XLSX" nasça fechado, o recurso é criado com uma regra CONTROLE_TOTAL só para a conta
administrativa principal (LOGIN_ADMIN; na falta dela, os superusuários). O SuperRoot libera
depois os usuários e setores na tela de Controle de acesso.

Revision ID: d4f7b2c9e1a3
Revises: c3e9a1f4b7d2
Create Date: 2026-09-26 02:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.core.configuracao import obter_configuracao

# Identificação da migração: esta revisão e a anterior
revision: str = "d4f7b2c9e1a3"
down_revision: str | Sequence[str] | None = "c3e9a1f4b7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "importacao-contratos"


def upgrade() -> None:
    """Cria o recurso e a regra que o deixa fechado (só a conta administrativa)."""
    conexao = op.get_bind()
    agora = datetime.now(UTC)
    # Idempotente: se o recurso já foi criado à mão na tela de ACL, não duplica
    recurso_id = conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :slug"), {"slug": SLUG})
    if recurso_id is None:
        recurso_id = conexao.scalar(
            sa.text(
                "INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES (:nome, :slug, :descricao, '/contratos', true, :agora, :agora) RETURNING id"
            ),
            {"nome": "Importação de contratos (XLSX)", "slug": SLUG, "agora": agora,
             "descricao": "Botão \"Importar XLSX\" da carteira de contratos: cadastro de contrato a partir da planilha modelo."},
        )
    # Recurso já com regras (criadas à mão): mantém como está
    if conexao.scalar(sa.text("SELECT count(*) FROM acl_regras WHERE recurso_id = :id"), {"id": recurso_id}):
        return
    # Conta administrativa principal; se ainda não existir, todos os superusuários
    usuarios = conexao.scalars(
        sa.text("SELECT id FROM usuarios WHERE lower(login) = lower(:login)"), {"login": obter_configuracao().login_admin}
    ).all() or conexao.scalars(sa.text("SELECT id FROM usuarios WHERE superusuario")).all()
    if not usuarios:
        # Banco sem nenhuma conta: o recurso fica sem regras (aberto) até o SuperRoot cadastrar uma
        return
    regra_id = conexao.scalar(
        sa.text("INSERT INTO acl_regras (recurso_id, nivel, criado_em, atualizado_em) VALUES (:id, 'CONTROLE_TOTAL', :agora, :agora) RETURNING id"),
        {"id": recurso_id, "agora": agora},
    )
    for usuario_id in usuarios:
        conexao.execute(sa.text("INSERT INTO acl_regras_usuarios (regra_id, usuario_id) VALUES (:regra, :usuario)"),
                        {"regra": regra_id, "usuario": usuario_id})


def downgrade() -> None:
    """Remove o recurso; as regras e seus vínculos saem em cascata."""
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :slug").bindparams(slug=SLUG))
