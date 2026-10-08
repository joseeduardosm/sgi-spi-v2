# Criado por José Eduardo Santana Martins
# Este arquivo serve para dar aos marcadores das tarefas o índice de cor da paleta de 12 cores.
"""tarefas: marcadores com cor da paleta

Revision ID: f1a4b8d2c6e7
Revises: e9f3a7c1b5d6
Create Date: 2026-10-08 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.tarefas.paleta import borda, indice_mais_proximo

revision: str = "f1a4b8d2c6e7"
down_revision: str | Sequence[str] | None = "e9f3a7c1b5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `cor_indice` e converte a cor hexadecimal de cada marcador para a cor mais próxima da paleta."""
    op.add_column("tarefas_marcadores", sa.Column("cor_indice", sa.Integer(), server_default="1", nullable=False))
    ligacao = op.get_bind()
    for marcador_id, cor in ligacao.execute(sa.text("SELECT id, cor FROM tarefas_marcadores")).all():
        indice = indice_mais_proximo(cor or "#5364ce")
        ligacao.execute(sa.text("UPDATE tarefas_marcadores SET cor_indice = :i, cor = :c WHERE id = :id"), {"i": indice, "c": borda(indice), "id": marcador_id})


def downgrade() -> None:
    """Remove o índice de cor (a cor hexadecimal da borda continua em `cor`)."""
    op.drop_column("tarefas_marcadores", "cor_indice")
