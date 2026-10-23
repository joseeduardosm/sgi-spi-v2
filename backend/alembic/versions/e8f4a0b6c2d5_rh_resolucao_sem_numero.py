# Criado por José Eduardo Santana Martins
# Este arquivo serve para parametrizar no RH o tipo do Protocolo que a resolução de nomeação consome e permitir a resolução sem número.

"""rh: tipo do Protocolo da resolução (parâmetro) e resolução sem número

Revision ID: e8f4a0b6c2d5
Revises: d7e3f9a5b1c4
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e8f4a0b6c2d5"
down_revision: str | Sequence[str] | None = "d7e3f9a5b1c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Parâmetro vazio = resolução sem número; as admissões já existentes seguem com número (`sem_numero` falso)."""
    op.add_column("rh_parametros", sa.Column("tipo_resolucao_protocolo_id", sa.Uuid(), sa.ForeignKey("protocolo_tipos.id", ondelete="SET NULL"), nullable=True))
    op.add_column("rh_admissoes", sa.Column("sem_numero", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("rh_admissoes", sa.Column("publicacao_anexo_id", sa.Uuid(), sa.ForeignKey("anexos.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    op.drop_column("rh_admissoes", "publicacao_anexo_id")
    op.drop_column("rh_admissoes", "sem_numero")
    op.drop_column("rh_parametros", "tipo_resolucao_protocolo_id")
