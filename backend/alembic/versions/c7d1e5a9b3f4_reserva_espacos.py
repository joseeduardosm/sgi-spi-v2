# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas do módulo Reserva de Espaços.
"""reserva de espaços: espaços, reservas, eventos, fiscais e configuração

Revision ID: c7d1e5a9b3f4
Revises: b2e6a0d4f8c1
Create Date: 2026-10-07 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7d1e5a9b3f4"
down_revision: str | Sequence[str] | None = "b2e6a0d4f8c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria as cinco tabelas e a linha única de configuração."""
    op.create_table(
        "reserva_espacos_espacos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("localizacao", sa.String(length=200), nullable=False),
        sa.Column("cor", sa.String(length=7), nullable=False),
        sa.Column("capacidade", sa.Integer(), nullable=True),
        sa.Column("equipamentos", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("origem_id", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nome"),
        sa.UniqueConstraint("origem_id"),
    )
    op.create_table(
        "reserva_espacos_reservas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("espaco_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fim", sa.Time(), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("responsavel_id", sa.Integer(), nullable=True),
        sa.Column("responsavel_nome", sa.String(length=200), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=False),
        sa.Column("participantes", sa.Integer(), nullable=True),
        sa.Column("solicitante_id", sa.Integer(), nullable=True),
        sa.Column("solicitante_nome", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("fiscal_id", sa.Integer(), nullable=True),
        sa.Column("fiscal_nome", sa.String(length=200), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=False),
        sa.Column("serie_id", sa.Uuid(), nullable=True),
        sa.Column("lembrete_enviado", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("origem_id", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("hora_fim > hora_inicio", name="ck_reserva_espacos_horario"),
        sa.ForeignKeyConstraint(["espaco_id"], ["reserva_espacos_espacos.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["responsavel_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["solicitante_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["fiscal_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("origem_id"),
    )
    op.create_index("ix_reserva_espacos_reservas_data", "reserva_espacos_reservas", ["data"])
    op.create_index("ix_reserva_espacos_reservas_status", "reserva_espacos_reservas", ["status"])
    op.create_index("ix_reserva_espacos_reservas_serie_id", "reserva_espacos_reservas", ["serie_id"])
    op.create_index("ix_reserva_espacos_reservas_solicitante_id", "reserva_espacos_reservas", ["solicitante_id"])
    op.create_index("ix_reserva_espacos_espaco_data", "reserva_espacos_reservas", ["espaco_id", "data", "status"])
    op.create_table(
        "reserva_espacos_eventos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reserva_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("usuario_nome", sa.String(length=200), nullable=False),
        sa.Column("detalhes", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reserva_id"], ["reserva_espacos_reservas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reserva_espacos_eventos_reserva_id", "reserva_espacos_eventos", ["reserva_id"])
    op.create_table(
        "reserva_espacos_fiscais",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("usuario_id"),
    )
    op.create_table(
        "reserva_espacos_configuracao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hora_abertura", sa.Time(), nullable=False),
        sa.Column("hora_fechamento", sa.Time(), nullable=False),
        sa.Column("antecedencia_minima_horas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duracao_maxima_horas", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO reserva_espacos_configuracao (id, hora_abertura, hora_fechamento) VALUES (1, '07:00', '19:00')")


def downgrade() -> None:
    """Remove as tabelas do módulo."""
    op.drop_table("reserva_espacos_configuracao")
    op.drop_table("reserva_espacos_fiscais")
    op.drop_table("reserva_espacos_eventos")
    op.drop_table("reserva_espacos_reservas")
    op.drop_table("reserva_espacos_espacos")
