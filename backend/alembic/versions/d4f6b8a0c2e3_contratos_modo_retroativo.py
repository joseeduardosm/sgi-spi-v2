"""
===============================================================================
ARQUIVO: d4f6b8a0c2e3_contratos_modo_retroativo.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Guardar a escolha "Cálculo manual ou automático?" da memória retroativa do
reajuste e da repactuação, e a diferença de cada mês no cálculo manual.

RESUMO TÉCNICO:
- `contratos_reajustes.modo_retroativo` e `contratos_repactuacoes.modo_retroativo`
  ("automatico" | "manual" | nulo = ainda não escolhido) e `modo_retroativo_em`
  (quando foi escolhido: memória gerada antes não vale para concluir).
- `contratos_diferencas_manuais.valores_meses` (JSON {competência: valor}).
- Dados: procedimento com diferença manual vira "manual"; os demais já
  concluídos ou cancelados viram "automatico"; os rascunhos sem diferença manual
  ficam nulos (o gestor escolhe na tela).

FINALIDADE DE NEGÓCIO:
Decisão do usuário (13/11/2026): a memória retroativa começa perguntando se o
cálculo é manual ou automático. No manual, o gestor informa a diferença mês a
mês e o sistema não calcula nada sozinho.

CONTEXTO NO SISTEMA:
Modelos em app/models/contratos/alteracoes.py; regras em
app/services/contratos/diferenca_manual.py.

Revision ID: d4f6b8a0c2e3
Revises: c3e5a7b9d1f2
Create Date: 2026-11-13
===============================================================================
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Identificação da migração: esta revisão e a anterior
revision: str = "d4f6b8a0c2e3"
down_revision: str | Sequence[str] | None = "c3e5a7b9d1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# JSON no SQLite, JSONB no PostgreSQL (mesmo tipo do modelo)
JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    # Nova coluna nas duas tabelas de procedimento
    for tabela in ("contratos_reajustes", "contratos_repactuacoes"):
        op.add_column(tabela, sa.Column("modo_retroativo", sa.String(12)))
        op.add_column(tabela, sa.Column("modo_retroativo_em", sa.DateTime(timezone=True)))
    op.add_column("contratos_diferencas_manuais", sa.Column("valores_meses", JSON, nullable=False, server_default=sa.text("'{}'")))
    # Quem já tem diferença manual estava, na prática, no cálculo manual
    op.execute("UPDATE contratos_reajustes SET modo_retroativo = 'manual' WHERE id IN "
               "(SELECT reajuste_id FROM contratos_diferencas_manuais WHERE reajuste_id IS NOT NULL)")
    op.execute("UPDATE contratos_repactuacoes SET modo_retroativo = 'manual' WHERE id IN "
               "(SELECT repactuacao_id FROM contratos_diferencas_manuais WHERE repactuacao_id IS NOT NULL)")
    # Os encerrados (concluídos ou cancelados) sem diferença manual usaram o automático
    for tabela in ("contratos_reajustes", "contratos_repactuacoes"):
        op.execute(f"UPDATE {tabela} SET modo_retroativo = 'automatico' WHERE modo_retroativo IS NULL AND situacao <> 'rascunho'")


def downgrade() -> None:
    op.drop_column("contratos_diferencas_manuais", "valores_meses")
    for tabela in ("contratos_reajustes", "contratos_repactuacoes"):
        op.drop_column(tabela, "modo_retroativo_em")
        op.drop_column(tabela, "modo_retroativo")
