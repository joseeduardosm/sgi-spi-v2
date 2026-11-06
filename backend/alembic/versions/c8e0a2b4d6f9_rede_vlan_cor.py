# Criado por José Eduardo Santana Martins
# Este arquivo serve para dar cor às VLANs (selo colorido no seletor da porta, como os marcadores das Tarefas).

"""rede: cor da VLAN

`rede_vlans.cor_indice` (0–11, a paleta dos marcadores das Tarefas). As VLANs já cadastradas ganham cores variadas pelo número
(`numero % 11 + 1`, de 1 a 11), para que VLANs vizinhas não fiquem iguais; a cor pode ser trocada depois pelo selo.

Revision ID: c8e0a2b4d6f9
Revises: b7d9f1a3c5e8
Create Date: 2026-11-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "c8e0a2b4d6f9"
down_revision: str | Sequence[str] | None = "b7d9f1a3c5e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rede_vlans", sa.Column("cor_indice", sa.Integer(), nullable=False, server_default="1"))
    op.execute("UPDATE rede_vlans SET cor_indice = numero % 11 + 1")


def downgrade() -> None:
    op.drop_column("rede_vlans", "cor_indice")
