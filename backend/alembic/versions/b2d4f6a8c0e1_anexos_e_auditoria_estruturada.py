"""anexos em disco e auditoria estruturada (histórico por campo)

Cria a tabela `anexos` (metadados dos PDFs guardados em disco) e acrescenta à `auditoria` a
identificação estruturada do alvo (`alvo_tipo`, `alvo_id`), o autor (`autor_id`) e o conteúdo
do ato em JSONB (`dados`), usados pelo histórico "quem alterou, quando, de → para".

Revision ID: b2d4f6a8c0e1
Revises: a1c3e5f7b9d2
Create Date: 2026-09-24 02:11:31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2d4f6a8c0e1"
down_revision: str | Sequence[str] | None = "a1c3e5f7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anexos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nome_original", sa.String(length=255), nullable=False),
        sa.Column("chave_armazenamento", sa.String(length=300), nullable=False),
        sa.Column("tipo_conteudo", sa.String(length=150), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("tamanho", sa.BigInteger(), nullable=False),
        sa.Column("categoria", sa.String(length=100), nullable=False),
        sa.Column("enviado_por_id", sa.Integer(), nullable=True),
        sa.Column("excluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["enviado_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chave_armazenamento"),
    )
    op.create_index("ix_anexos_categoria", "anexos", ["categoria"])
    op.create_index("ix_anexos_sha256", "anexos", ["sha256"])

    op.add_column("auditoria", sa.Column("autor_id", sa.Integer(), nullable=True))
    op.add_column("auditoria", sa.Column("alvo_tipo", sa.String(length=60), nullable=True))
    op.add_column("auditoria", sa.Column("alvo_id", sa.String(length=64), nullable=True))
    op.add_column("auditoria", sa.Column("dados", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index("ix_auditoria_alvo", "auditoria", ["alvo_tipo", "alvo_id", "ocorrido_em"])


def downgrade() -> None:
    op.drop_index("ix_auditoria_alvo", table_name="auditoria")
    op.drop_column("auditoria", "dados")
    op.drop_column("auditoria", "alvo_id")
    op.drop_column("auditoria", "alvo_tipo")
    op.drop_column("auditoria", "autor_id")
    op.drop_index("ix_anexos_sha256", table_name="anexos")
    op.drop_index("ix_anexos_categoria", table_name="anexos")
    op.drop_table("anexos")
