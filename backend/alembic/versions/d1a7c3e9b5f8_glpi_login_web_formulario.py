# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar na integração com o GLPI o login web da conta de serviço e o id do formulário de nomeações (envio do formulário pelo SGI).

"""glpi: login web da conta de serviço e formulário de nomeações

Revision ID: d1a7c3e9b5f8
Revises: c0f6b2d8e4a7
Create Date: 2026-10-22
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d1a7c3e9b5f8"
down_revision: str | Sequence[str] | None = "c0f6b2d8e4a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("integracao_glpi", sa.Column("usuario_web", sa.String(150), nullable=False, server_default=""))
    op.add_column("integracao_glpi", sa.Column("senha_web_cifrada", sa.String(600), nullable=False, server_default=""))
    op.add_column("integracao_glpi", sa.Column("formulario_nomeacao_id", sa.Integer(), nullable=False, server_default="8"))


def downgrade() -> None:
    with op.batch_alter_table("integracao_glpi") as lote:
        lote.drop_column("formulario_nomeacao_id")
        lote.drop_column("senha_web_cifrada")
        lote.drop_column("usuario_web")
