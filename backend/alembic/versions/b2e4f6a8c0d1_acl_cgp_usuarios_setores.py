# Criado por José Eduardo Santana Martins
# Este arquivo serve para dar à CGP controle total sobre usuários e setores pela ACL.
"""acl: CGP com CONTROLE_TOTAL em `usuarios` e `setores`

As gravações de usuários e setores passaram a aceitar CONTROLE_TOTAL na ACL (antes, só SuperRoot). Esta migração cria,
nos dois recursos, uma regra CONTROLE_TOTAL para o setor "Coordenadoria de Gestão de Pessoas" (membros do setor).
Com a regra, os recursos viram lista positiva: só a CGP e os SuperRoot leem e alteram. Recurso que já tiver regras
não é tocado. Se o setor não existir, nada é criado (a CGP pode ser configurada depois em Controle de acesso).

Revision ID: b2e4f6a8c0d1
Revises: a1d3f5b7c9e2
Create Date: 2026-09-29 22:00:00
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b2e4f6a8c0d1"
down_revision: str | Sequence[str] | None = "a1d3f5b7c9e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RECURSOS = {"usuarios": "Usuários", "setores": "Setores"}
SETOR_CGP = "Coordenadoria de Gestão de Pessoas"


def upgrade() -> None:
    """Cria a regra CONTROLE_TOTAL da CGP nos recursos que ainda não têm regras."""
    conexao = op.get_bind()
    setor_id = conexao.scalar(sa.text("SELECT id FROM setores WHERE lower(trim(nome)) = lower(:nome)"), {"nome": SETOR_CGP})
    if setor_id is None:
        return
    agora = datetime.now(timezone.utc)
    for slug, nome in RECURSOS.items():
        recurso_id = conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :slug"), {"slug": slug})
        if recurso_id is None:
            recurso_id = conexao.scalar(
                sa.text("INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                        "VALUES (:nome, :slug, '', '', true, :agora, :agora) RETURNING id"),
                {"nome": nome, "slug": slug, "agora": agora},
            )
        if conexao.scalar(sa.text("SELECT count(*) FROM acl_regras WHERE recurso_id = :id"), {"id": recurso_id}):
            continue
        regra_id = conexao.scalar(
            sa.text("INSERT INTO acl_regras (recurso_id, nivel, criado_em, atualizado_em) VALUES (:id, 'CONTROLE_TOTAL', :agora, :agora) RETURNING id"),
            {"id": recurso_id, "agora": agora},
        )
        conexao.execute(sa.text("INSERT INTO acl_regras_setores (regra_id, setor_id) VALUES (:regra, :setor)"), {"regra": regra_id, "setor": setor_id})


def downgrade() -> None:
    """Remove as regras da CGP criadas aqui (os recursos voltam a ficar abertos para leitura; gravação só SuperRoot)."""
    conexao = op.get_bind()
    conexao.execute(sa.text(
        "DELETE FROM acl_regras WHERE id IN ("
        " SELECT r.id FROM acl_regras r JOIN acl_recursos c ON c.id = r.recurso_id"
        " JOIN acl_regras_setores rs ON rs.regra_id = r.id JOIN setores s ON s.id = rs.setor_id"
        " WHERE c.slug IN ('usuarios', 'setores') AND r.nivel = 'CONTROLE_TOTAL' AND lower(trim(s.nome)) = lower(:nome))"
    ), {"nome": SETOR_CGP})
