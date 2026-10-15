# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a autoridade do despacho no contrato e liberar o tipo de modelo "despacho".
"""contratos: autoridade do despacho e modelo de despacho

`contratos.autoridade_despacho_id` (usuário que autoriza o pagamento) e o tipo `despacho` em `contratos_modelos` (máscara do despacho do consolidado).

Revision ID: a8c4e6f1b3d5
Revises: f7b3d5e9c2a4
Create Date: 2026-10-15 16:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a8c4e6f1b3d5'
down_revision: Union[str, Sequence[str], None] = 'f7b3d5e9c2a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('contratos', sa.Column('autoridade_despacho_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_contratos_autoridade_despacho', 'contratos', 'usuarios', ['autoridade_despacho_id'], ['id'], ondelete='SET NULL')
    with op.batch_alter_table('contratos_modelos') as lote:
        lote.drop_constraint('ck_contratos_modelos_tipo', type_='check')
        lote.create_check_constraint('ck_contratos_modelos_tipo', "tipo IN ('checklist', 'formulario', 'portaria', 'despacho')")


def downgrade() -> None:
    op.execute("DELETE FROM contratos_modelos WHERE tipo = 'despacho'")
    with op.batch_alter_table('contratos_modelos') as lote:
        lote.drop_constraint('ck_contratos_modelos_tipo', type_='check')
        lote.create_check_constraint('ck_contratos_modelos_tipo', "tipo IN ('checklist', 'formulario', 'portaria')")
    op.drop_constraint('fk_contratos_autoridade_despacho', 'contratos', type_='foreignkey')
    op.drop_column('contratos', 'autoridade_despacho_id')
