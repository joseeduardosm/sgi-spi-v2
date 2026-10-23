# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar de novo nos parâmetros do RH o setor do Serviço de Apoio Administrativo (SAA), que vê os tipos do Protocolo restritos a um setor.

"""rh: setor do Serviço de Apoio Administrativo (SAA) como parâmetro, para a visibilidade dos tipos restritos do Protocolo

Revision ID: d7e3f9a5b1c4
Revises: c6d2e8f4a0b3
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d7e3f9a5b1c4"
down_revision: str | Sequence[str] | None = "c6d2e8f4a0b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Coluna opcional, já preenchida com o setor do SAA encontrado pelo nome; vazia, vale o nome da configuração."""
    op.add_column("rh_parametros", sa.Column("setor_apoio_administrativo_id", sa.Integer(), sa.ForeignKey("setores.id", ondelete="SET NULL"), nullable=True))
    conexao = op.get_bind()
    setor_id = next((i for i, n in conexao.execute(sa.text("SELECT id, nome FROM setores")).all() if (n or "").strip().lower() == "serviço de apoio administrativo"), None)
    if setor_id is not None:
        conexao.execute(sa.text("UPDATE rh_parametros SET setor_apoio_administrativo_id = :s"), {"s": setor_id})


def downgrade() -> None:
    op.drop_column("rh_parametros", "setor_apoio_administrativo_id")
