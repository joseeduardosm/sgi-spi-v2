# Criado por José Eduardo Santana Martins
# Este arquivo serve para ampliar os modos de porta da rede (hybrid, QinQ, DTP e roteada), com VLAN de voz, IP da porta roteada e VLANs sem tag.

"""rede: modos de porta das marcas em uso (Cisco, Huawei, 3Com/H3C)

- `rede_portas.modo` passa de 6 para 20 caracteres e aceita `hybrid`, `dot1q_tunnel`, `dinamico_auto`, `dinamico_desejavel` e `roteada`;
- `rede_portas.vlan_voz_id` (VLAN de voz) e `rede_portas.ip_interface` (IP da porta roteada);
- `rede_portas_vlans.com_tag`: as VLANs que já existiam eram todas com tag (trunk) e ficam `true`; `false` é a VLAN sem tag da hybrid.

Revision ID: f2b4d6e8a0c1
Revises: e1a3c5d7f9b2
Create Date: 2026-11-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f2b4d6e8a0c1"
down_revision: str | Sequence[str] | None = "e1a3c5d7f9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MODOS = "'access', 'trunk', 'hybrid', 'dot1q_tunnel', 'dinamico_auto', 'dinamico_desejavel', 'roteada'"


def upgrade() -> None:
    """Amplia o modo e cria os campos novos (nada muda nas portas que já existem)."""
    with op.batch_alter_table("rede_portas") as tabela:
        tabela.drop_constraint("ck_rede_portas_modo", type_="check")
        tabela.alter_column("modo", type_=sa.String(20), existing_type=sa.String(6), existing_nullable=False, existing_server_default="access")
        tabela.create_check_constraint("ck_rede_portas_modo", f"modo IN ({MODOS})")
        tabela.add_column(sa.Column("vlan_voz_id", sa.Uuid, sa.ForeignKey("rede_vlans.id", ondelete="SET NULL", name="fk_rede_portas_vlan_voz")))
        tabela.add_column(sa.Column("ip_interface", sa.String(49), nullable=False, server_default=""))
    op.add_column("rede_portas_vlans", sa.Column("com_tag", sa.Boolean, nullable=False, server_default=sa.true()))


def downgrade() -> None:
    """Volta a access/trunk: os modos novos viram access; as VLANs sem tag da hybrid saem."""
    op.execute("DELETE FROM rede_portas_vlans WHERE com_tag = false")
    op.drop_column("rede_portas_vlans", "com_tag")
    op.execute("UPDATE rede_portas SET modo = 'trunk' WHERE modo IN ('hybrid', 'dinamico_auto', 'dinamico_desejavel')")
    op.execute("UPDATE rede_portas SET modo = 'access' WHERE modo NOT IN ('access', 'trunk')")
    with op.batch_alter_table("rede_portas") as tabela:
        tabela.drop_column("ip_interface")
        tabela.drop_column("vlan_voz_id")
        tabela.drop_constraint("ck_rede_portas_modo", type_="check")
        tabela.alter_column("modo", type_=sa.String(6), existing_type=sa.String(20), existing_nullable=False, existing_server_default="access")
        tabela.create_check_constraint("ck_rede_portas_modo", "modo IN ('access', 'trunk')")
