# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar nos parâmetros do RH o setor de apoio administrativo (SAA), antes definido só pelo nome no código.

"""rh: setor de apoio administrativo (SAA) como parâmetro

Revision ID: f7c3e9a5b2d4
Revises: e6b2d8f4a1c3
Create Date: 2026-10-22
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

    conexao = op.get_bind()
    nome = obter_configuracao().setor_apoio_administrativo.strip().lower()
    setor_id = next((i for i, n in conexao.execute(sa.text("SELECT id, nome FROM setores")).all() if (n or "").strip().lower() == nome), None)
    if setor_id is not None:
        conexao.execute(sa.text("UPDATE rh_parametros SET setor_apoio_administrativo_id = :s"), {"s": setor_id})


def downgrade() -> None:
    op.drop_column("rh_parametros", "setor_apoio_administrativo_id")
