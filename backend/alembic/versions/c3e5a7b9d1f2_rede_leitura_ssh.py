"""
===============================================================================
ARQUIVO: c3e5a7b9d1f2_rede_leitura_ssh.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Guardar o acesso SSH só leitura de cada equipamento de rede e as leituras
(cargas) feitas por ele.

RESUMO TÉCNICO:
- `rede_equipamentos`: acesso_usuario, acesso_senha (cifrada pela aplicação),
  acesso_porta (22) e acesso_tipo (tipo do Netmiko que funcionou).
- Tabela `rede_leituras`: equipamento, quando, por quem, o resultado (JSON) e
  quando/quem aplicou no cadastro.

FINALIDADE DE NEGÓCIO:
Decisão do usuário (13/11/2026): no cadastro de switch, AP ou roteador, o SGI
lê o equipamento por SSH e oferece aplicar o que leu, em vez de digitar tudo.

CONTEXTO NO SISTEMA:
Modelos em app/models/rede.py; leitura em app/services/rede/leitura_ssh.py.

Revision ID: c3e5a7b9d1f2
Revises: f7a1c3e5b9d2
Create Date: 2026-11-13
===============================================================================
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão e a anterior
revision: str = "c3e5a7b9d1f2"
down_revision: str | Sequence[str] | None = "f7a1c3e5b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# JSON no SQLite, JSONB no PostgreSQL (mesmo tipo do modelo)
JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("rede_equipamentos", sa.Column("acesso_usuario", sa.String(120), nullable=False, server_default=""))
    op.add_column("rede_equipamentos", sa.Column("acesso_senha", sa.Text(), nullable=False, server_default=""))
    op.add_column("rede_equipamentos", sa.Column("acesso_porta", sa.Integer(), nullable=False, server_default="22"))
    op.add_column("rede_equipamentos", sa.Column("acesso_tipo", sa.String(40), nullable=False, server_default=""))
    op.create_table(
        "rede_leituras",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("equipamento_id", sa.Uuid(), sa.ForeignKey("rede_equipamentos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lido_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lido_por", sa.String(250), nullable=False, server_default=""),
        sa.Column("resultado", JSON, nullable=False),
        sa.Column("aplicada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aplicada_por", sa.String(250), nullable=False, server_default=""),
    )
    op.create_index("ix_rede_leituras_equipamento_id", "rede_leituras", ["equipamento_id"])


def downgrade() -> None:
    op.drop_index("ix_rede_leituras_equipamento_id", table_name="rede_leituras")
    op.drop_table("rede_leituras")
    for coluna in ("acesso_tipo", "acesso_porta", "acesso_senha", "acesso_usuario"):
        op.drop_column("rede_equipamentos", coluna)
