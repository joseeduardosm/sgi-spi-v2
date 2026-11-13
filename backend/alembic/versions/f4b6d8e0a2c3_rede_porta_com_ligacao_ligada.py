"""
===============================================================================
ARQUIVO: f4b6d8e0a2c3_rede_porta_com_ligacao_ligada.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic de dados que marca como "ligada" (status up) toda porta de
rede que participa de uma conexão.

RESUMO TÉCNICO:
Um único UPDATE em rede_portas: passa a 'up' toda porta cujo id aparece como
porta_a_id ou porta_b_id em rede_conexoes e que ainda não estava up. Não muda a
estrutura do banco. O downgrade não faz nada, pois o status anterior (vazio)
não foi guardado.

FINALIDADE DE NEGÓCIO:
Na carga por LLDP, as portas dos access points, dos Dell e do 3Com
(equipamentos não lidos por SSH) ficaram sem status, embora o LLDP só enxergue
cabo ativo. A regra é: porta com equipamento ligado está necessariamente
ligada, e a topologia passa a mostrar isso corretamente.

CONTEXTO NO SISTEMA:
Tabelas rede_portas e rede_conexoes do módulo Rede (topologia e carga por
LLDP). Aplicada com 'alembic upgrade head' (o instalador e a atualização do
sistema rodam esse comando).

Revision ID: f4b6d8e0a2c3
Revises: e2a4c6e8b0d1
Create Date: 2026-11-03

===============================================================================
"""

from collections.abc import Sequence

from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f4b6d8e0a2c3"
down_revision: str | Sequence[str] | None = "e2a4c6e8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Toda porta numa conexão passa a "ligada"."""
    # rede_conexoes liga porta_a a porta_b (porta_b pode ser nula, ex.: cabo para um
    # equipamento sem portas cadastradas). O UNION junta os dois lados numa lista só.
    op.execute("""
        UPDATE rede_portas SET status = 'up'
        WHERE (status IS NULL OR status <> 'up')
          AND id IN (SELECT porta_a_id FROM rede_conexoes UNION SELECT porta_b_id FROM rede_conexoes WHERE porta_b_id IS NOT NULL)
    """)


def downgrade() -> None:
    """Sem volta: o status anterior (vazio) não foi guardado e não faz falta."""
