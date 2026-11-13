"""
===============================================================================
ARQUIVO: f7b3d5e9c2a4_execucao_cadin_depois_do_checklist.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic de dados que ajusta as competências em andamento à nova ordem
das etapas: retenção, checklist e só então CADIN, última etapa antes do
consolidado.

RESUMO TÉCNICO:
Dois UPDATE em contratos_competencias: competências paradas em etapa_atual
'cadin' sem retencao_concluida_em voltam para 'retencao'; as que ainda estão em
'cadin' sem checklist_concluido_em voltam para 'checklist'. O downgrade não
desfaz nada.

FINALIDADE DE NEGÓCIO:
Competência é o mês de execução do contrato que será medido e pago. CADIN é o
cadastro federal de inadimplentes, consultado antes do pagamento. A consulta ao
CADIN só abre com as etapas anteriores prontas, então competências que estavam
adiantadas voltam para a etapa pendente.

CONTEXTO NO SISTEMA:
Tabela contratos_competencias; fluxo de execução em
app/api/routes/contratos/execucao.py e serviço de competências. Aplicada com
'alembic upgrade head' (o instalador e a atualização do sistema rodam esse
comando).

Revision ID: f7b3d5e9c2a4
Revises: e6a2c4d8b1f3
Create Date: 2026-10-15 15:00:00

===============================================================================
"""

from typing import Sequence, Union

from alembic import op

revision: str = 'f7b3d5e9c2a4'
down_revision: Union[str, Sequence[str], None] = 'e6a2c4d8b1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Devolve à etapa pendente as competências paradas em cadin antes da hora.

    A retenção é conferida primeiro: se ela não terminou, a competência volta para
    "retencao"; se terminou mas o checklist não, volta para "checklist".
    """
    op.execute("UPDATE contratos_competencias SET etapa_atual = 'retencao' WHERE etapa_atual = 'cadin' AND retencao_concluida_em IS NULL")
    op.execute("UPDATE contratos_competencias SET etapa_atual = 'checklist' WHERE etapa_atual = 'cadin' AND checklist_concluido_em IS NULL")


def downgrade() -> None:
    """Sem volta: a etapa anterior de cada competência não foi guardada."""
    pass
