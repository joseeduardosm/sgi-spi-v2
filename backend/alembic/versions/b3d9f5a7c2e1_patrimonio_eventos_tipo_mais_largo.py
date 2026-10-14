# Criado por José Eduardo Santana Martins
# Este arquivo serve para alargar o tipo do evento do histórico do bem, que não comportava "classificacao_pendente" (22 caracteres).
"""patrimonio_eventos.tipo: de 20 para 40 caracteres

Os tipos `classificacao_pendente` e `classificacao_recusada` têm 22 caracteres e o envio de uma lista de inservíveis/extraviados falhava com
"value too long for type character varying(20)". Alargar um varchar não reescreve a tabela e não dispara o gatilho de imutabilidade do histórico.

Revision ID: b3d9f5a7c2e1
Revises: a2c8e4f6b1d9
Create Date: 2026-10-13 19:40:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3d9f5a7c2e1'
down_revision: Union[str, Sequence[str], None] = 'a2c8e4f6b1d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('patrimonio_eventos', 'tipo', existing_type=sa.String(20), type_=sa.String(40), existing_nullable=False)


def downgrade() -> None:
    op.alter_column('patrimonio_eventos', 'tipo', existing_type=sa.String(40), type_=sa.String(20), existing_nullable=False)
