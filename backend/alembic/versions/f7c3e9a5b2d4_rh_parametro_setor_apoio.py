"""
===============================================================================
ARQUIVO: f7c3e9a5b2d4_rh_parametro_setor_apoio.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que guarda nos parâmetros do RH o setor de apoio
administrativo (SAA), antes definido só pelo nome no código.

RESUMO TÉCNICO:
Cria rh_parametros.setor_apoio_administrativo_id (opcional, chave estrangeira
para setores com ON DELETE SET NULL) e já preenche com o setor cujo nome,
ignorando maiúsculas, é "serviço de apoio administrativo". Vazia, vale o setor
de nome igual ao configurado (comportamento anterior). O downgrade remove a
coluna.

FINALIDADE DE NEGÓCIO:
O SAA tem papel especial no SGI (por exemplo, vê os tipos do Protocolo
restritos a um setor). Com o parâmetro, a mudança de nome do setor não quebra
esse papel e o administrador escolhe o setor na tela de parâmetros do RH.

CONTEXTO NO SISTEMA:
Tabelas rh_parametros e setores; parâmetros do módulo RH
(app/api/routes/rh.py). Aplicada com 'alembic upgrade head' (o instalador e a
atualização do sistema rodam esse comando).

Revision ID: f7c3e9a5b2d4
Revises: e6b2d8f4a1c3
Create Date: 2026-10-22

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f7c3e9a5b2d4"
down_revision: str | Sequence[str] | None = "e6b2d8f4a1c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Coluna opcional: vazia, vale o setor de nome igual ao configurado (comportamento anterior). Já preenche com o setor encontrado pelo nome."""
    op.add_column("rh_parametros", sa.Column("setor_apoio_administrativo_id", sa.Integer(), sa.ForeignKey("setores.id", ondelete="SET NULL"), nullable=True))
    from app.core.configuracao import obter_configuracao

    # Procura em Python (sem diferenciar maiúsculas e espaços nas pontas) o setor com
    # o nome que o código usava antes; se achar, grava o id dele nos parâmetros do RH
    conexao = op.get_bind()
    nome = "serviço de apoio administrativo"
    setor_id = next((i for i, n in conexao.execute(sa.text("SELECT id, nome FROM setores")).all() if (n or "").strip().lower() == nome), None)
    if setor_id is not None:
        conexao.execute(sa.text("UPDATE rh_parametros SET setor_apoio_administrativo_id = :s"), {"s": setor_id})


def downgrade() -> None:
    """Remove a coluna (volta a valer só o nome do setor)."""
    op.drop_column("rh_parametros", "setor_apoio_administrativo_id")
