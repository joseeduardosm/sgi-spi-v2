# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a RDM (Requisição de Mudança) das tarefas.

"""tarefas: RDM (Requisição de Mudança)

`tarefas_rdms`: uma por tarefa, com o número do Protocolo (tipo "RDM SGI", criado pelo serviço no primeiro uso), a situação
(rascunho, pendente, aprovada, reprovada, concluída), os campos do formulário (JSON), quem enviou e quem decidiu (com cargo e setor
para o rodapé do PDF), o motivo da reprovação e o PDF gerado na aprovação.

Revision ID: d1f3a5b7c9e2
Revises: c8e0a2b4d6f9
Create Date: 2026-11-06
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d1f3a5b7c9e2"
down_revision: str | Sequence[str] | None = "c8e0a2b4d6f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tarefas_rdms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tarefa_id", sa.Uuid(), nullable=False),
        sa.Column("numero_protocolo_id", sa.Uuid(), nullable=True),
        sa.Column("numero", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("titulo", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("situacao", sa.String(length=10), nullable=False, server_default="rascunho"),
        sa.Column("dados", sa.JSON(), nullable=False),
        sa.Column("enviada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enviada_por_id", sa.Integer(), nullable=True),
        sa.Column("enviada_por_nome", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("decidida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decidida_por_id", sa.Integer(), nullable=True),
        sa.Column("decidida_por_nome", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("decidida_por_cargo", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("decidida_por_setor", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("motivo_reprovacao", sa.Text(), nullable=False, server_default=""),
        sa.Column("pdf_anexo_id", sa.Uuid(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("situacao IN ('rascunho', 'pendente', 'aprovada', 'reprovada', 'concluida')", name="ck_tarefas_rdms_situacao"),
        sa.ForeignKeyConstraint(["decidida_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["enviada_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["numero_protocolo_id"], ["protocolo_numeros.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pdf_anexo_id"], ["anexos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tarefa_id"], ["tarefas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero_protocolo_id"),
        sa.UniqueConstraint("tarefa_id"),
    )


def downgrade() -> None:
    op.drop_table("tarefas_rdms")
