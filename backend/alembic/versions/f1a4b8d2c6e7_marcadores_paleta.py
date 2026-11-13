"""
===============================================================================
ARQUIVO: f1a4b8d2c6e7_marcadores_paleta.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que dá aos marcadores das tarefas o índice de cor da paleta
fixa de 12 cores (tarefas: marcadores com cor da paleta).

RESUMO TÉCNICO:
Cria a coluna tarefas_marcadores.cor_indice (inteiro, padrão 1) e, para cada
marcador existente, calcula com indice_mais_proximo a cor da paleta mais
parecida com a cor hexadecimal livre que ele tinha, gravando o índice e a cor
de borda oficial (borda). O downgrade só apaga cor_indice.

FINALIDADE DE NEGÓCIO:
Marcadores (etiquetas coloridas das tarefas) passam a usar só as cores da
paleta do sistema, que funcionam nos temas claro e escuro, sem perder a cor
aproximada que cada equipe já tinha escolhido.

CONTEXTO NO SISTEMA:
Usa app/services/tarefas/paleta.py; afeta a tabela tarefas_marcadores do módulo
Tarefas. Aplicada com 'alembic upgrade head' (o instalador e a atualização do
sistema rodam esse comando).

Revision ID: f1a4b8d2c6e7
Revises: e9f3a7c1b5d6
Create Date: 2026-10-08 09:00:00

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.tarefas.paleta import borda, indice_mais_proximo

# Identificação da migração para o Alembic (esta revisão e a anterior na cadeia)
revision: str = "f1a4b8d2c6e7"
down_revision: str | Sequence[str] | None = "e9f3a7c1b5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `cor_indice` e converte a cor hexadecimal de cada marcador para a cor mais próxima da paleta."""
    op.add_column("tarefas_marcadores", sa.Column("cor_indice", sa.Integer(), server_default="1", nullable=False))
    # op.get_bind() devolve a conexão aberta pelo Alembic, para ler e gravar dados
    # (não só mudar o esquema). Cada marcador recebe o índice da cor mais parecida
    # da paleta, e a coluna "cor" passa a ser a cor de borda oficial desse índice.
    # Marcador sem cor usa o azul "#5364ce" como ponto de partida.
    ligacao = op.get_bind()
    for marcador_id, cor in ligacao.execute(sa.text("SELECT id, cor FROM tarefas_marcadores")).all():
        indice = indice_mais_proximo(cor or "#5364ce")
        ligacao.execute(sa.text("UPDATE tarefas_marcadores SET cor_indice = :i, cor = :c WHERE id = :id"), {"i": indice, "c": borda(indice), "id": marcador_id})


def downgrade() -> None:
    """Remove o índice de cor (a cor hexadecimal da borda continua em `cor`)."""
    op.drop_column("tarefas_marcadores", "cor_indice")
