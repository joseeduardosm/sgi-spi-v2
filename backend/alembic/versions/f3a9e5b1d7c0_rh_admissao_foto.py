"""
===============================================================================
ARQUIVO: f3a9e5b1d7c0_rh_admissao_foto.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que guarda na admissão do RH a foto da pessoa (rh: foto da
admissão).

RESUMO TÉCNICO:
Cria a coluna rh_admissoes.foto_anexo_id, chave estrangeira para anexos.id com
ON DELETE SET NULL. O downgrade remove a coluna.

FINALIDADE DE NEGÓCIO:
A foto enviada na admissão de um novo servidor é aproveitada no cadastro do
GLPI e na intranet, sem pedir a imagem de novo.

CONTEXTO NO SISTEMA:
Tabelas rh_admissoes e anexos; rotas app/api/routes/rh_admissao.py. Aplicada
com 'alembic upgrade head' (o instalador e a atualização do sistema rodam esse
comando).

Revision ID: f3a9e5b1d7c0
Revises: e2f8d4a0c6b9
Create Date: 2026-10-23

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f3a9e5b1d7c0"
down_revision: str | Sequence[str] | None = "e2f8d4a0c6b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria rh_admissoes.foto_anexo_id, apontando para o arquivo guardado em anexos."""
    # ondelete="SET NULL": se o anexo for apagado, a admissão fica só sem foto
    op.add_column("rh_admissoes", sa.Column("foto_anexo_id", sa.Uuid(), sa.ForeignKey("anexos.id", ondelete="SET NULL")))


def downgrade() -> None:
    """Remove a coluna da foto (o arquivo em anexos não é apagado)."""
    with op.batch_alter_table("rh_admissoes") as lote:
        lote.drop_column("foto_anexo_id")
