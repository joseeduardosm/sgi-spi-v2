"""
===============================================================================
ARQUIVO: e5a7c9b1d3f4_contratos_sem_efeito.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Permitir tornar sem efeito um evento já concluído do contrato (reajuste,
repactuação, aditamento/supressão e prorrogação), guardando quem fez, quando e
o motivo.

RESUMO TÉCNICO:
- Situação `sem_efeito` nos check constraints de `contratos_reajustes`,
  `contratos_repactuacoes` e `contratos_alteracoes`.
- Colunas `sem_efeito_em`, `sem_efeito_por_id`, `sem_efeito_por_nome` e
  `sem_efeito_motivo` nessas três tabelas e em
  `contratos_prorrogacoes_processos` (a prorrogação desfeita fica no processo).
- Dados: processos de prorrogação "desfeito" (desfeitos antes desta versão)
  passam a "sem_efeito", com o motivo "Desfeita antes do registro de motivo".

FINALIDADE DE NEGÓCIO:
Decisão do usuário (13/11/2026): o evento desfeito continua no histórico com o
selo "Sem efeito", com quem fez, quando e o motivo, e fica auditável.

CONTEXTO NO SISTEMA:
Modelos em app/models/contratos/alteracoes.py; regras em
app/services/contratos/servico_sem_efeito.py.

Revision ID: e5a7c9b1d3f4
Revises: d4f6b8a0c2e3
Create Date: 2026-11-13
===============================================================================
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e5a7c9b1d3f4"
down_revision: str | Sequence[str] | None = "d4f6b8a0c2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tabela → (nome do check constraint da situação, situações antigas)
SITUACOES = {
    "contratos_reajustes": ("ck_contratos_reajustes_situacao", "'rascunho', 'concluido', 'cancelado'"),
    "contratos_repactuacoes": ("ck_contratos_repactuacoes_situacao", "'rascunho', 'concluido', 'cancelado'"),
    "contratos_alteracoes": ("ck_contratos_alteracoes_situacao", "'rascunho', 'aguardando_ciencias', 'concluida', 'cancelada'"),
}
TABELAS_COLUNAS = [*SITUACOES, "contratos_prorrogacoes_processos"]


def upgrade() -> None:
    # 1) A situação nova entra nos check constraints (batch: funciona também no SQLite dos testes)
    for tabela, (nome, antigas) in SITUACOES.items():
        with op.batch_alter_table(tabela) as lote:
            lote.drop_constraint(nome, type_="check")
            lote.create_check_constraint(nome, f"situacao IN ({antigas}, 'sem_efeito')")
    # 2) Quem tornou sem efeito, quando e por quê
    for tabela in TABELAS_COLUNAS:
        op.add_column(tabela, sa.Column("sem_efeito_em", sa.DateTime(timezone=True)))
        op.add_column(tabela, sa.Column("sem_efeito_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")))
        op.add_column(tabela, sa.Column("sem_efeito_por_nome", sa.String(250), nullable=False, server_default=""))
        op.add_column(tabela, sa.Column("sem_efeito_motivo", sa.Text(), nullable=False, server_default=""))
    # 3) Prorrogações desfeitas antes desta versão: mesma situação nova, sem motivo registrado
    op.execute("UPDATE contratos_prorrogacoes_processos SET situacao = 'sem_efeito', "
               "sem_efeito_motivo = 'Desfeita antes do registro de motivo' WHERE situacao = 'desfeito'")


def downgrade() -> None:
    op.execute("UPDATE contratos_prorrogacoes_processos SET situacao = 'desfeito' WHERE situacao = 'sem_efeito'")
    for tabela in TABELAS_COLUNAS:
        for coluna in ("sem_efeito_motivo", "sem_efeito_por_nome", "sem_efeito_por_id", "sem_efeito_em"):
            op.drop_column(tabela, coluna)
    for tabela, (nome, antigas) in SITUACOES.items():
        op.execute(f"UPDATE {tabela} SET situacao = 'concluido' WHERE situacao = 'sem_efeito'".replace("'concluido'", "'concluida'" if tabela == "contratos_alteracoes" else "'concluido'"))
        with op.batch_alter_table(tabela) as lote:
            lote.drop_constraint(nome, type_="check")
            lote.create_check_constraint(nome, f"situacao IN ({antigas})")
