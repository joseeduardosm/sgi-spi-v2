# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar, em cada ocorrência do diário de bordo, a competência que ela afeta (independente da data).
"""diário de bordo: competência afetada

`contratos_diario_ocorrencias.competencia_afetada` (dia 1 do mês). As ocorrências já registradas ficam com a competência regular cujo período
contém a data (como as glosas já valiam), ou o mês da data quando não há competência gerada.

Revision ID: b9d5f7a2c4e6
Revises: a8c4e6f1b3d5
Create Date: 2026-10-15 19:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b9d5f7a2c4e6'
down_revision: Union[str, Sequence[str], None] = 'a8c4e6f1b3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('contratos_diario_ocorrencias', sa.Column('competencia_afetada', sa.Date(), nullable=True))
    op.create_index('ix_contratos_diario_ocorrencias_competencia_afetada', 'contratos_diario_ocorrencias', ['competencia_afetada'])
    conexao = op.get_bind()
    conexao.execute(sa.text(
        "UPDATE contratos_diario_ocorrencias o SET competencia_afetada = COALESCE("
        "(SELECT c.competencia FROM contratos_competencias c WHERE c.contrato_id = o.contrato_id AND c.tipo = 'regular' "
        "AND o.data_ocorrencia BETWEEN c.periodo_inicio AND c.periodo_fim ORDER BY c.periodo_inicio LIMIT 1), "
        "date_trunc('month', o.data_ocorrencia)::date)"
    ) if conexao.dialect.name == 'postgresql' else sa.text(
        "UPDATE contratos_diario_ocorrencias SET competencia_afetada = date(data_ocorrencia, 'start of month')"
    ))


def downgrade() -> None:
    op.drop_index('ix_contratos_diario_ocorrencias_competencia_afetada', table_name='contratos_diario_ocorrencias')
    op.drop_column('contratos_diario_ocorrencias', 'competencia_afetada')
