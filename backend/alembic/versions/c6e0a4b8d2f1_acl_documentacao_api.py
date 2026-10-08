# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar o recurso de ACL que libera a documentação da API (Swagger e ReDoc).
"""acl: recurso `documentacao-api` (Swagger, ReDoc e especificação OpenAPI)

As páginas da documentação deixam de ser públicas: só usuários logados com o recurso `documentacao-api` ≥ LEITURA as veem. O recurso nasce
**fechado** (regra CONTROLE_TOTAL só para a conta administrativa principal; na falta dela, os superusuários); o SuperRoot libera depois
os demais na tela de Controle de acesso.

Revision ID: c6e0a4b8d2f1
Revises: b5d9f3a7c1e2
Create Date: 2026-10-06 12:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.core.configuracao import obter_configuracao

# Identificação da migração: esta revisão e a anterior
revision: str = "c6e0a4b8d2f1"
down_revision: str | Sequence[str] | None = "b5d9f3a7c1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "documentacao-api"


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
                "VALUES (:nome, :slug, :descricao, '/api/documentacao', true, :agora, :agora) RETURNING id"
            ),
            {"nome": "Documentação da API", "slug": SLUG, "agora": agora,
             "descricao": "Páginas Swagger (/api/documentacao), ReDoc (/api/redoc) e a especificação OpenAPI (/api/openapi.json)."},
        )
    # Recurso já com regras (criadas à mão): mantém como está
    if conexao.scalar(sa.text("SELECT count(*) FROM acl_regras WHERE recurso_id = :id"), {"id": recurso_id}):
        return
    usuarios = conexao.scalars(
        sa.text("SELECT id FROM usuarios WHERE lower(login) = lower(:login)"), {"login": obter_configuracao().login_admin}
    ).all() or conexao.scalars(sa.text("SELECT id FROM usuarios WHERE superusuario")).all()
    if not usuarios:
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
