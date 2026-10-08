# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela da política de SLA (com os prazos padrão) e o recurso de ACL "sla" (gestão fechada).
"""SLA: tabela `sla_politicas`, prazos padrão e recurso de ACL `sla`

Prazos padrão em dias úteis (resposta/resolução): tarefas crítica 1/3, alta 2/5, normal 3/10, baixa 5/20; melhorias 3/15. O recurso `sla` nasce
**fechado** (CONTROLE_TOTAL só para a conta administrativa principal; na falta dela, os superusuários); o SuperRoot libera depois os demais.

Revision ID: b4d7f1a9c2e6
Revises: a3c6e9b1d4f7
Create Date: 2026-10-08 20:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.core.configuracao import obter_configuracao

# Identificação da migração: esta revisão e a anterior
revision: str = "b4d7f1a9c2e6"
down_revision: str | Sequence[str] | None = "a3c6e9b1d4f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "sla"
PADROES = [("tarefas", "critica", 1, 3), ("tarefas", "alta", 2, 5), ("tarefas", "normal", 3, 10), ("tarefas", "baixa", 5, 20), ("melhorias", "", 3, 15)]


def upgrade() -> None:
    """Cria a tabela, grava os prazos padrão e cria o recurso fechado."""
    op.create_table(
        "sla_politicas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("modulo", sa.String(length=20), nullable=False),
        sa.Column("prioridade", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("dias_uteis_resposta", sa.Integer(), nullable=False),
        sa.Column("dias_uteis_resolucao", sa.Integer(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("modulo", "prioridade", name="uq_sla_politicas_modulo_prioridade"),
        sa.CheckConstraint("modulo IN ('tarefas', 'melhorias')", name="ck_sla_politicas_modulo"),
        sa.CheckConstraint("dias_uteis_resposta >= 0 AND dias_uteis_resolucao >= dias_uteis_resposta", name="ck_sla_politicas_dias"),
    )
    conexao = op.get_bind()
    for modulo, prioridade, resposta, resolucao in PADROES:
        conexao.execute(sa.text("INSERT INTO sla_politicas (modulo, prioridade, dias_uteis_resposta, dias_uteis_resolucao) VALUES (:m, :p, :r, :s)"),
                        {"m": modulo, "p": prioridade, "r": resposta, "s": resolucao})
    agora = datetime.now(UTC)
    recurso_id = conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :slug"), {"slug": SLUG})
    if recurso_id is None:
        recurso_id = conexao.scalar(
            sa.text("INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                    "VALUES (:nome, :slug, :descricao, '/admin/sla', true, :agora, :agora) RETURNING id"),
            {"nome": "SLA de prazos", "slug": SLUG, "agora": agora, "descricao": "Política de prazos de resposta e de resolução (dias úteis) de Tarefas e Melhorias."},
        )
    if conexao.scalar(sa.text("SELECT count(*) FROM acl_regras WHERE recurso_id = :id"), {"id": recurso_id}):
        return
    usuarios = conexao.scalars(sa.text("SELECT id FROM usuarios WHERE lower(login) = lower(:login)"), {"login": obter_configuracao().login_admin}).all() \
        or conexao.scalars(sa.text("SELECT id FROM usuarios WHERE superusuario")).all()
    if not usuarios:
        return
    regra_id = conexao.scalar(sa.text("INSERT INTO acl_regras (recurso_id, nivel, criado_em, atualizado_em) VALUES (:id, 'CONTROLE_TOTAL', :agora, :agora) RETURNING id"),
                              {"id": recurso_id, "agora": agora})
    for usuario_id in usuarios:
        conexao.execute(sa.text("INSERT INTO acl_regras_usuarios (regra_id, usuario_id) VALUES (:regra, :usuario)"), {"regra": regra_id, "usuario": usuario_id})


def downgrade() -> None:
    """Remove o recurso (as regras saem em cascata) e a tabela."""
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :slug").bindparams(slug=SLUG))
    op.drop_table("sla_politicas")
