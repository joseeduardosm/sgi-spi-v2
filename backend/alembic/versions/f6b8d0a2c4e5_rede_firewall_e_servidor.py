"""
===============================================================================
ARQUIVO: f6b8d0a2c4e5_rede_firewall_e_servidor.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Aceitar os tipos de equipamento "firewall" e "servidor" no módulo Rede.

RESUMO TÉCNICO:
Migração Alembic: troca o CHECK ck_rede_equipamentos_tipo da tabela
rede_equipamentos para incluir 'firewall' e 'servidor'. O downgrade só volta
se não houver equipamento desses tipos (senão o CHECK antigo falharia).

FINALIDADE DE NEGÓCIO:
Pedido do usuário (17/11/2026): cadastrar firewall e servidor como
equipamentos de rede, tratados como roteador e "outro" (modelo de face, IP
de gerência, rack e U, ligados abaixo de um switch de acesso).

CONTEXTO NO SISTEMA:
Os tipos ficam em app/models/rede.py (TIPOS_EQUIPAMENTO) e
app/schemas/rede.py (TipoEquipamento).

===============================================================================
"""
from alembic import op

# Identificadores da revisão (o Alembic usa para encadear as migrações)
revision = "f6b8d0a2c4e5"
down_revision = "e5a7c9b1d3f4"
branch_labels = None
depends_on = None

TIPOS_ANTIGOS = "'switch', 'patch_panel', 'roteador', 'access_point', 'outro'"
TIPOS = "'switch', 'patch_panel', 'roteador', 'access_point', 'firewall', 'servidor', 'outro'"


def upgrade() -> None:
    # batch_alter_table: no SQLite (testes) a tabela é recriada; no PostgreSQL vira ALTER TABLE
    with op.batch_alter_table("rede_equipamentos") as tabela:
        tabela.drop_constraint("ck_rede_equipamentos_tipo", type_="check")
        tabela.create_check_constraint("ck_rede_equipamentos_tipo", f"tipo IN ({TIPOS})")


def downgrade() -> None:
    with op.batch_alter_table("rede_equipamentos") as tabela:
        tabela.drop_constraint("ck_rede_equipamentos_tipo", type_="check")
        tabela.create_check_constraint("ck_rede_equipamentos_tipo", f"tipo IN ({TIPOS_ANTIGOS})")
