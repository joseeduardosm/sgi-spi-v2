"""
===============================================================================
ARQUIVO: f2b4d6e8a0c1_rede_modos_de_porta.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que amplia os modos de porta do módulo Rede para as marcas em
uso (Cisco, Huawei, 3Com/H3C): hybrid, QinQ, DTP e porta roteada, com VLAN de
voz, IP da porta roteada e VLANs sem tag.

RESUMO TÉCNICO:
- rede_portas.modo passa de 6 para 20 caracteres e a check constraint aceita
  hybrid, dot1q_tunnel, dinamico_auto, dinamico_desejavel e roteada;
- novas colunas rede_portas.vlan_voz_id (VLAN de voz) e
  rede_portas.ip_interface (IP da porta roteada);
- rede_portas_vlans.com_tag: as VLANs que já existiam eram todas com tag
  (trunk) e ficam true; false é a VLAN sem tag da porta hybrid. O downgrade
  converte os modos novos em access/trunk e apaga as VLANs sem tag.

FINALIDADE DE NEGÓCIO:
Permite documentar no SGI a configuração real das portas dos switches da SPI,
sem forçar tudo a access ou trunk, o que ajuda o suporte a entender a topologia
e diagnosticar problemas de rede.

CONTEXTO NO SISTEMA:
Tabelas rede_portas, rede_vlans e rede_portas_vlans; modelos do módulo Rede e
rotas app/api/routes/rede.py. Aplicada com 'alembic upgrade head' (o instalador
e a atualização do sistema rodam esse comando).

Revision ID: f2b4d6e8a0c1
Revises: e1a3c5d7f9b2
Create Date: 2026-11-02

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f2b4d6e8a0c1"
down_revision: str | Sequence[str] | None = "e1a3c5d7f9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Lista de modos aceitos pela check constraint da coluna rede_portas.modo
MODOS = "'access', 'trunk', 'hybrid', 'dot1q_tunnel', 'dinamico_auto', 'dinamico_desejavel', 'roteada'"


def upgrade() -> None:
    """Amplia o modo e cria os campos novos (nada muda nas portas que já existem)."""
    # batch_alter_table agrupa várias alterações na mesma tabela. A check constraint
    # precisa sair antes de alargar a coluna e voltar depois já com os modos novos.
    with op.batch_alter_table("rede_portas") as tabela:
        tabela.drop_constraint("ck_rede_portas_modo", type_="check")
        tabela.alter_column("modo", type_=sa.String(20), existing_type=sa.String(6), existing_nullable=False, existing_server_default="access")
        tabela.create_check_constraint("ck_rede_portas_modo", f"modo IN ({MODOS})")
        tabela.add_column(sa.Column("vlan_voz_id", sa.Uuid, sa.ForeignKey("rede_vlans.id", ondelete="SET NULL", name="fk_rede_portas_vlan_voz")))
        tabela.add_column(sa.Column("ip_interface", sa.String(49), nullable=False, server_default=""))
    op.add_column("rede_portas_vlans", sa.Column("com_tag", sa.Boolean, nullable=False, server_default=sa.true()))


def downgrade() -> None:
    """Volta a access/trunk: os modos novos viram access; as VLANs sem tag da hybrid saem."""
    # Sem a coluna com_tag não há como guardar VLAN sem tag: essas ligações são apagadas.
    # Modos que transportam várias VLANs viram trunk; os demais (QinQ, roteada) viram access.
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
