# Criado por José Eduardo Santana Martins
# Este arquivo serve para passar a faixa reservada do Protocolo do Serviço de Apoio Administrativo (SAA) para a Coordenadoria de Gestão e Infraestrutura (CGI).

"""protocolo: faixa reservada passa a ser da CGI

Revision ID: b5c1d7e3f9a2
Revises: a4b0f6c2e8d1
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b5c1d7e3f9a2"
down_revision: str | Sequence[str] | None = "a4b0f6c2e8d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _setor_por_nome(conexao, nome: str) -> int | None:
    return next((i for i, n in conexao.execute(sa.text("SELECT id, nome FROM setores")).all() if (n or "").strip().lower() == nome), None)


def upgrade() -> None:
    """Renomeia a coluna do parâmetro e aponta para o setor da CGI (se existir); sem o setor, vale o nome da configuração."""
    op.alter_column("rh_parametros", "setor_apoio_administrativo_id", new_column_name="setor_reserva_protocolo_id")
    conexao = op.get_bind()
    setor_id = _setor_por_nome(conexao, "coordenadoria de gestão e infraestrutura")
    if setor_id is not None:
        conexao.execute(sa.text("UPDATE rh_parametros SET setor_reserva_protocolo_id = :s"), {"s": setor_id})


def downgrade() -> None:
    op.alter_column("rh_parametros", "setor_reserva_protocolo_id", new_column_name="setor_apoio_administrativo_id")
    conexao = op.get_bind()
    setor_id = _setor_por_nome(conexao, "serviço de apoio administrativo")
    if setor_id is not None:
        conexao.execute(sa.text("UPDATE rh_parametros SET setor_apoio_administrativo_id = :s"), {"s": setor_id})
