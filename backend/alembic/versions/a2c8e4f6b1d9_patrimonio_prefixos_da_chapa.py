# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar os prefixos das chapas do Patrimônio e passar as chapas numéricas existentes para o formato SPI + 6 dígitos.
"""patrimonio: prefixos da chapa

- Tabela `patrimonio_prefixos` (parâmetro editável) com SPI (padrão), SLT, DERSA, ARTESP e ARSESP.
- As chapas só com números passam a SPI + 6 dígitos (ex.: 00241 → SPI000241), com um evento "alterou" no histórico de cada bem.

Revision ID: a2c8e4f6b1d9
Revises: f1a7c3e9b4d6
Create Date: 2026-10-13 19:00:00
"""
import uuid
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a2c8e4f6b1d9'
down_revision: Union[str, Sequence[str], None] = 'f1a7c3e9b4d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PREFIXOS = ('SPI', 'SLT', 'DERSA', 'ARTESP', 'ARSESP')


def upgrade() -> None:
    tabela = op.create_table(
        'patrimonio_prefixos',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('codigo', sa.String(20), nullable=False, unique=True),
        sa.Column('padrao', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    )
    agora = datetime.now(UTC)
    op.bulk_insert(tabela, [{'id': uuid.uuid4(), 'codigo': c, 'padrao': c == 'SPI', 'ativo': True, 'criado_em': agora} for c in PREFIXOS])

    conexao = op.get_bind()
    bens = conexao.execute(sa.text("SELECT id, chapa FROM patrimonio_bens WHERE chapa ~ '^[0-9]+$'")).all()
    for bem_id, chapa in bens:
        nova = 'SPI' + chapa.zfill(6)
        conexao.execute(sa.text('UPDATE patrimonio_bens SET chapa = :c, chapa_chave = :k WHERE id = :i'), {'c': nova, 'k': nova.lower(), 'i': bem_id})
        conexao.execute(sa.text(
            "INSERT INTO patrimonio_eventos (id, bem_id, tipo, campo, valor_anterior, valor_novo, autor_nome, origem, texto, ocorrido_em) "
            "VALUES (:id, :bem, 'alterou', 'chapa', :ant, :novo, 'Sistema', 'migracao', 'Chapa passou ao formato com prefixo (SPI + 6 dígitos).', :quando)"),
            {'id': uuid.uuid4(), 'bem': bem_id, 'ant': chapa, 'novo': nova, 'quando': agora})


def downgrade() -> None:
    # As chapas com prefixo continuam como estão (não há como separar o que foi migrado do que foi cadastrado depois)
    op.drop_table('patrimonio_prefixos')
