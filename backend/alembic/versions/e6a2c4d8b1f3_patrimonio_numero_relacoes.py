# Criado por José Eduardo Santana Martins
# Este arquivo serve para numerar (#n) as listas de inservíveis, de extraviados e as baixas do Patrimônio.
"""patrimônio: número de exibição das relações

Coluna `numero` em `patrimonio_classificacoes` e `patrimonio_baixas`, numeradas juntas pela data de criação (sequência única).

Revision ID: e6a2c4d8b1f3
Revises: d5f1b3a9c8e2
Create Date: 2026-10-15 14:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e6a2c4d8b1f3'
down_revision: Union[str, Sequence[str], None] = 'd5f1b3a9c8e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELAS = ('patrimonio_classificacoes', 'patrimonio_baixas')


def upgrade() -> None:
    for t in TABELAS:
        op.add_column(t, sa.Column('numero', sa.Integer(), nullable=True))
    # Numera o que já existe, das mais antigas para as mais novas, nas duas tabelas juntas
    conexao = op.get_bind()
    linhas = conexao.execute(sa.text(
        "SELECT 'patrimonio_classificacoes' AS t, id, criada_em FROM patrimonio_classificacoes "
        "UNION ALL SELECT 'patrimonio_baixas', id, criada_em FROM patrimonio_baixas ORDER BY criada_em, id"
    )).fetchall()
    for numero, (tabela, id_, _) in enumerate(linhas, start=1):
        conexao.execute(sa.text(f"UPDATE {tabela} SET numero = :n WHERE id = :i"), {"n": numero, "i": id_})
    for t in TABELAS:
        with op.batch_alter_table(t) as lote:
            lote.alter_column('numero', existing_type=sa.Integer(), nullable=False)
            lote.create_unique_constraint(f'uq_{t}_numero', ['numero'])


def downgrade() -> None:
    for t in TABELAS:
        with op.batch_alter_table(t) as lote:
            lote.drop_constraint(f'uq_{t}_numero', type_='unique')
            lote.drop_column('numero')
