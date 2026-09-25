"""contratos: exclusão em cascata de itens de reajuste/alteração e da seleção de NEs

Com RESTRICT, excluir um contrato com reajuste, aditamento ou competência paga falhava no
PostgreSQL. A exclusão de NE ligada a competência continua barrada pelo serviço.

Revision ID: 84d049d7fa1a
Revises: 65c4a5320944
Create Date: 2026-09-24 03:25:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "84d049d7fa1a"
down_revision: str | Sequence[str] | None = "65c4a5320944"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (tabela, coluna, tabela referenciada)
CHAVES = (
    ("contratos_alteracoes_itens", "item_id", "contratos_itens"),
    ("contratos_reajustes_itens", "item_id", "contratos_itens"),
    ("contratos_competencias_notas", "nota_id", "contratos_notas_empenho"),
)


def _trocar(regra: str) -> None:
    for tabela, coluna, referencia in CHAVES:
        nome = f"{tabela}_{coluna}_fkey"
        op.drop_constraint(nome, tabela, type_="foreignkey")
        op.create_foreign_key(nome, tabela, referencia, [coluna], ["id"], ondelete=regra)


def upgrade() -> None:
    _trocar("CASCADE")


def downgrade() -> None:
    _trocar("RESTRICT")
