# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar o setor sistêmico "Equipes de contratos" e preenchê-lo com quem já integra a equipe de algum contrato.
"""setor sistêmico Equipes de contratos

O setor é mantido pelo sistema (`setor_equipes.sincronizar`) a cada alteração da equipe de um contrato. Aqui ele é criado e recebe os
usuários ativos com designação vigente hoje.

Revision ID: a7c3e9f1b5d2
Revises: f4b0d8c6e2a5
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c3e9f1b5d2"
down_revision = "f4b0d8c6e2a5"
branch_labels = None
depends_on = None

NOME = "Equipes de contratos"


def upgrade() -> None:
    conexao = op.get_bind()
    setor_id = conexao.execute(sa.text("SELECT id FROM setores WHERE nome = :n AND sistemico"), {"n": NOME}).scalar()
    if setor_id is None:
        setor_id = conexao.execute(
            sa.text("INSERT INTO setores (nome, sistemico, ativo, criado_em, atualizado_em) VALUES (:n, true, true, now(), now()) RETURNING id"), {"n": NOME}
        ).scalar()
    conexao.execute(
        sa.text(
            "INSERT INTO membros_setor (setor_id, usuario_id, criado_em) "
            "SELECT DISTINCT :s, e.usuario_id, now() FROM contratos_equipe e JOIN usuarios u ON u.id = e.usuario_id "
            "WHERE u.ativo AND (e.valido_de IS NULL OR e.valido_de <= now()) AND (e.valido_ate IS NULL OR e.valido_ate > now()) "
            "ON CONFLICT DO NOTHING"
        ),
        {"s": setor_id},
    )


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM setores WHERE nome = :n AND sistemico"), {"n": NOME})
