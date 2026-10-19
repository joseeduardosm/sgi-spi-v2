# Criado por José Eduardo Santana Martins
# Este arquivo serve para preparar as portarias de designação em etapas (nomeações, ciência e reserva do número só no fim).

"""portarias em etapas: nomeações com ciência, número e sigla opcionais, anexo da evidência

Revision ID: e9b3c5a7d1f2
Revises: d7a2f5c8b1e4
Create Date: 2026-10-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e9b3c5a7d1f2"
down_revision: str | Sequence[str] | None = "d7a2f5c8b1e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Número e exercício passam a ser opcionais (só existem depois da autoridade); cria as nomeações e o anexo da evidência."""
    op.alter_column("contratos_portarias", "numero", existing_type=sa.Integer(), nullable=True)
    op.alter_column("contratos_portarias", "exercicio", existing_type=sa.Integer(), nullable=True)
    op.alter_column("contratos_portarias", "status", existing_type=sa.String(20), type_=sa.String(24), existing_nullable=False)
    op.add_column("contratos_portarias", sa.Column("evidencia_anexo_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_contratos_portarias_evidencia", "contratos_portarias", "anexos", ["evidencia_anexo_id"], ["id"], ondelete="SET NULL")
    op.create_table(
        "contratos_portarias_nomeacoes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("portaria_id", sa.Uuid(), sa.ForeignKey("contratos_portarias.id", ondelete="CASCADE"), nullable=False),
        sa.Column("papel", sa.String(40), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nome_usuario", sa.String(200), nullable=False),
        sa.Column("ciente_em", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("portaria_id", "papel", name="uq_nomeacao_portaria_papel"),
    )
    op.create_index("ix_contratos_portarias_nomeacoes_portaria_id", "contratos_portarias_nomeacoes", ["portaria_id"])
    op.create_index("ix_contratos_portarias_nomeacoes_usuario_id", "contratos_portarias_nomeacoes", ["usuario_id"])
    # Portarias do fluxo antigo ainda em andamento (aguardando aceite, devolvidas ou aceitas) não têm ciências: ficam canceladas e o número
    # reservado precisa ser liberado à mão no Protocolo, se houver. As publicadas e as canceladas seguem como estavam.
    op.execute(sa.text("UPDATE contratos_portarias SET status = 'cancelada', motivo = 'Cancelada na migração para o novo fluxo de portarias.' "
                       "WHERE status IN ('aguardando_aceite', 'devolvida', 'aceita')"))


def downgrade() -> None:
    """Desfaz as nomeações e volta número e exercício a obrigatórios (portarias sem número recebem 0)."""
    op.drop_table("contratos_portarias_nomeacoes")
    op.drop_constraint("fk_contratos_portarias_evidencia", "contratos_portarias", type_="foreignkey")
    op.drop_column("contratos_portarias", "evidencia_anexo_id")
    op.execute(sa.text("UPDATE contratos_portarias SET numero = 0 WHERE numero IS NULL"))
    op.execute(sa.text("UPDATE contratos_portarias SET exercicio = 0 WHERE exercicio IS NULL"))
    op.execute(sa.text("UPDATE contratos_portarias SET status = 'cancelada' WHERE char_length(status) > 20"))
    op.alter_column("contratos_portarias", "status", existing_type=sa.String(24), type_=sa.String(20), existing_nullable=False)
    op.alter_column("contratos_portarias", "exercicio", existing_type=sa.Integer(), nullable=False)
    op.alter_column("contratos_portarias", "numero", existing_type=sa.Integer(), nullable=False)
