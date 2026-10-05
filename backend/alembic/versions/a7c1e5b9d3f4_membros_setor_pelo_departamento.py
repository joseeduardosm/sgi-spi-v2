# Criado por José Eduardo Santana Martins
# Este arquivo serve para incluir como membros do setor os usuários cujo Departamento já aponta para ele.
"""setores: membros pelo Departamento do perfil

O Departamento passou a definir a participação no setor de mesmo nome (a ACL consulta `membros_setor`,
não o texto do perfil). Esta migração aplica a regra aos usuários que já tinham o Departamento válido
mas nenhum vínculo: sem ela, eles continuariam sem os acessos liberados ao setor.

Revision ID: a7c1e5b9d3f4
Revises: f6b9d4e8a3c2
Create Date: 2026-10-05 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a7c1e5b9d3f4"
down_revision: str | Sequence[str] | None = "f6b9d4e8a3c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Insere o vínculo usuário ↔ setor (institucional e ativo) pelo nome; repetir não duplica."""
    op.execute(sa.text(
        "INSERT INTO membros_setor (setor_id, usuario_id, criado_em) "
        "SELECT s.id, u.id, now() FROM usuarios u "
        "JOIN setores s ON lower(trim(s.nome)) = lower(trim(u.departamento)) "
        "WHERE s.ativo AND NOT s.sistemico AND trim(u.departamento) <> '' "
        "ON CONFLICT (setor_id, usuario_id) DO NOTHING"
    ))


def downgrade() -> None:
    """Sem desfazer: não há como distinguir os vínculos criados aqui dos feitos à mão."""
