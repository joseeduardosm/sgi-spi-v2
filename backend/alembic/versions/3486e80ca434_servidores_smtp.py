"""
===============================================================================
ARQUIVO: 3486e80ca434_servidores_smtp.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Criar a tabela de configuração dos servidores SMTP (envio de e-mail),
cadastrados pelo SuperRoot no mesmo molde dos diretórios LDAP.

RESUMO TÉCNICO:
Cria `servidores_smtp` com endereço, porta, tipo de segurança (nenhuma,
starttls, ssl), usuário, senha cifrada, remetente, tempo limite e o resultado
do último teste de conexão e do último envio de teste. Um índice único parcial
(`WHERE ativo`) garante no máximo um servidor ativo.

FINALIDADE DE NEGÓCIO:
Todos os avisos por e-mail do SGI (prazos, notificações, documentos) saem pelo
servidor ativo. Guardar o resultado dos testes ajuda o administrador a
diagnosticar falhas de envio sem acessar o servidor.

CONTEXTO NO SISTEMA:
Modelo de servidores SMTP em `app/models`, serviço de e-mail e rotas de
configuração (SuperRoot = administrador com a coluna `superusuario`).

Revision ID: 3486e80ca434
Revises: 9f9b0de79c5a
Create Date: 2026-09-25 17:17:43

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior (o Alembic encadeia as migrações por esses ids)
revision: str = "3486e80ca434"
down_revision: str | Sequence[str] | None = "9f9b0de79c5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# upgrade() aplica esta mudança no banco (alembic upgrade) e downgrade() a
# desfaz (alembic downgrade), voltando à revisão anterior.
#
# As funções op.* do Alembic executam comandos de estrutura (DDL) no banco:
# create_table, add_column, alter_column, create_index, drop_* etc.
def upgrade() -> None:
    """Cria a tabela `servidores_smtp` e o índice que garante um único servidor
    ativo.
    """
    op.create_table(
        "servidores_smtp",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("servidor", sa.String(length=255), nullable=False),
        sa.Column("porta", sa.Integer(), nullable=False),
        sa.Column("seguranca", sa.String(length=10), nullable=False),
        sa.Column("usuario", sa.String(length=254), nullable=False),
        sa.Column("senha_cifrada", sa.Text(), nullable=True),
        sa.Column("remetente_email", sa.String(length=254), nullable=False),
        sa.Column("remetente_nome", sa.String(length=150), nullable=False),
        sa.Column("responder_para", sa.String(length=254), nullable=False),
        sa.Column("tempo_limite_segundos", sa.Integer(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("ultimo_teste_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_teste_ok", sa.Boolean(), nullable=True),
        sa.Column("ultima_latencia_ms", sa.Integer(), nullable=True),
        sa.Column("ultimo_erro", sa.Text(), nullable=True),
        sa.Column("ultimo_envio_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_envio_ok", sa.Boolean(), nullable=True),
        sa.Column("ultimo_envio_para", sa.String(length=254), nullable=True),
        sa.Column("ultimo_envio_mensagem", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("seguranca IN ('nenhuma', 'starttls', 'ssl')", name="ck_servidores_smtp_seguranca"),
        sa.PrimaryKeyConstraint("id", name="servidores_smtp_pkey"),
    )
    # Índice único parcial: só entram no índice as linhas com ativo verdadeiro,
    # então duas linhas ativas violam a unicidade, mas várias inativas
    # convivem.
    op.create_index(
        "ux_servidores_smtp_unico_ativo", "servidores_smtp", ["ativo"], unique=True,
        postgresql_where=sa.text("ativo"), sqlite_where=sa.text("ativo"),
    )


def downgrade() -> None:
    """Remove o índice e a tabela dos servidores SMTP."""
    op.drop_index("ux_servidores_smtp_unico_ativo", table_name="servidores_smtp")
    op.drop_table("servidores_smtp")
