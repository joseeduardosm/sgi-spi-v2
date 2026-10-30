# Criado por José Eduardo Santana Martins
# Este arquivo serve para marcar os documentos incluídos durante o processo nos checklists da execução mensal e da admissão do RH.
"""checklists "a partir de…": documentos incluídos durante o processo

O checklist aplicado vira ponto de partida: na execução mensal do contrato (`contratos_competencias_documentos`)
e na admissão do RH (`rh_admissao_documentos`) a equipe inclui documentos que não estavam no modelo.
O incluído nunca é obrigatório, pode ser excluído enquanto a etapa estiver aberta e não muda o modelo.

Revision ID: b8d2f4a6c9e1
Revises: a7c3e9b5d1f4
Create Date: 2026-10-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# ────────────────────────────────────────────────────────────────────────────
revision = "b8d2f4a6c9e1"
down_revision = "a7c3e9b5d1f4"
branch_labels = None
depends_on = None
# ────────────────────────────────────────────────────────────────────────────


def upgrade() -> None:
    # Execução mensal do contrato: o PDF do incluído vai no `anexo_id` que já existe
    op.add_column("contratos_competencias_documentos", sa.Column("incluido_no_processo", sa.Boolean(), nullable=False, server_default=sa.false(),
                                                                 comment="Incluído durante o processo (fora do checklist do contrato)."))
    op.add_column("contratos_competencias_documentos", sa.Column("incluido_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True))
    op.add_column("contratos_competencias_documentos", sa.Column("incluido_em", sa.DateTime(timezone=True), nullable=True))

    # Admissão do RH: descrição e arquivo próprios (o comprovante continua sendo o do envio ao Portal de Indicações)
    op.add_column("rh_admissao_documentos", sa.Column("incluido_no_processo", sa.Boolean(), nullable=False, server_default=sa.false(),
                                                      comment="Incluído durante a admissão (fora do checklist do cargo)."))
    op.add_column("rh_admissao_documentos", sa.Column("detalhe", sa.String(1000), nullable=False, server_default=""))
    op.add_column("rh_admissao_documentos", sa.Column("arquivo_anexo_id", UUID(as_uuid=True), sa.ForeignKey("anexos.id", ondelete="SET NULL"), nullable=True))
    op.add_column("rh_admissao_documentos", sa.Column("incluido_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True))
    op.add_column("rh_admissao_documentos", sa.Column("incluido_por_nome", sa.String(200), nullable=False, server_default=""))
    op.add_column("rh_admissao_documentos", sa.Column("incluido_em", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for coluna in ("incluido_em", "incluido_por_nome", "incluido_por_id", "arquivo_anexo_id", "detalhe", "incluido_no_processo"):
        op.drop_column("rh_admissao_documentos", coluna)
    for coluna in ("incluido_em", "incluido_por_id", "incluido_no_processo"):
        op.drop_column("contratos_competencias_documentos", coluna)
