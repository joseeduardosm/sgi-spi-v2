# Criado por José Eduardo Santana Martins
# Este arquivo serve para marcar qual reajuste já pagou o retroativo de cada competência regular,
# fechando o limbo dos meses entre reajustes de vigências distintas.
"""competencia: diferenca_coberta_por_reajuste_id

Marca qual reajuste já calculou e pagou o retroativo de uma competência regular.
Resolve o "limbo" de meses entre dois reajustes consecutivos de vigências distintas
(ex.: meses 8–2 de uma vigência que começa em agosto quando o reajuste tem
referência em março do ano seguinte).

Revision ID: d1e3f5a7b9c2
Revises: c6e0a4b8d2f5
Create Date: 2026-10-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# ────────────────────────────────────────────────────────────────────────────
revision = "d1e3f5a7b9c2"
down_revision = "c6e0a4b8d2f5"
branch_labels = None
depends_on = None
# ────────────────────────────────────────────────────────────────────────────


def upgrade() -> None:
    # Novo campo: FK opcional para o reajuste que cobriu esta competência
    op.add_column(
        "contratos_competencias",
        sa.Column(
            "diferenca_coberta_por_reajuste_id",
            UUID(as_uuid=True),
            sa.ForeignKey("contratos_reajustes.id", ondelete="SET NULL"),
            nullable=True,
            comment="Reajuste que calculou e pagou o retroativo desta competência regular; NULL = ainda sem cobertura.",
        ),
    )
    op.create_index(
        "ix_contratos_competencias_diferenca_coberta_por_reajuste_id",
        "contratos_competencias",
        ["diferenca_coberta_por_reajuste_id"],
    )

    # Backfill: marcar competências já cobertas pelos reajustes concluídos existentes.
    # Usa o filtro ANTIGO (sequencia_vigencia + >= mes_referencia) para reproduzir
    # exatamente o que _competencias_medidas fazia antes desta mudança.
    op.execute("""
        UPDATE contratos_competencias c
           SET diferenca_coberta_por_reajuste_id = r.id
          FROM contratos_reajustes r
         WHERE r.situacao = 'concluido'
           AND r.retroativo IS NOT TRUE
           AND c.contrato_id = r.contrato_id
           AND c.tipo = 'regular'
           AND c.sequencia_vigencia = r.sequencia_vigencia
           AND c.competencia >= r.mes_referencia
           AND c.medicao_concluida_em IS NOT NULL
           AND c.diferenca_coberta_por_reajuste_id IS NULL
    """)


def downgrade() -> None:
    op.drop_index(
        "ix_contratos_competencias_diferenca_coberta_por_reajuste_id",
        table_name="contratos_competencias",
    )
    op.drop_column("contratos_competencias", "diferenca_coberta_por_reajuste_id")
