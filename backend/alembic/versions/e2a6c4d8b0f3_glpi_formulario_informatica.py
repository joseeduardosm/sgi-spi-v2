# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar na integração com o GLPI os parâmetros do formulário "Informática" (grupo, SLAs, modelo e prefixo do título).
"""integração GLPI: parâmetros do formulário "Informática" (id 3)

O chamado aberto pelo SGI passa a ser montado como o formulário "Informática" do GLPI: título "Informática | assunto", grupo
SUPORTE atribuído, SLA de atendimento e de solução e modelo de chamado padrão. Os valores iniciais são os do formulário.

Revision ID: e2a6c4d8b0f3
Revises: d1f4b8a2e6c9
Create Date: 2026-10-05 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e2a6c4d8b0f3"
down_revision: str | Sequence[str] | None = "d1f4b8a2e6c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Acrescenta as colunas, já com os valores do formulário #3 do GLPI."""
    op.add_column("integracao_glpi", sa.Column("prefixo_titulo", sa.String(length=80), nullable=False, server_default="Informática"))
    op.add_column("integracao_glpi", sa.Column("grupo_atribuido_id", sa.Integer(), nullable=True, server_default="4"))
    op.add_column("integracao_glpi", sa.Column("sla_atendimento_id", sa.Integer(), nullable=True, server_default="2"))
    op.add_column("integracao_glpi", sa.Column("sla_solucao_id", sa.Integer(), nullable=True, server_default="1"))
    op.add_column("integracao_glpi", sa.Column("template_id", sa.Integer(), nullable=True, server_default="1"))


def downgrade() -> None:
    """Remove as colunas."""
    for coluna in ("template_id", "sla_solucao_id", "sla_atendimento_id", "grupo_atribuido_id", "prefixo_titulo"):
        op.drop_column("integracao_glpi", coluna)
