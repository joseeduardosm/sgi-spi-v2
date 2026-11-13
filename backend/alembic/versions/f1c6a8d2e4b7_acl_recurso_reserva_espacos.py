"""
===============================================================================
ARQUIVO: f1c6a8d2e4b7_acl_recurso_reserva_espacos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que cadastra na ACL o recurso reserva-espacos, que já era
usado nas rotas mas não aparecia na tela de Controle de acesso.

RESUMO TÉCNICO:
As rotas do módulo já conferiam exigir_acl("reserva-espacos", ...), mas o
recurso nunca foi cadastrado em acl_recursos, por isso não aparecia na lista de
módulos dos perfis nem em Regras. O upgrade insere o recurso só se o slug ainda
não existir (idempotente); o downgrade apaga o recurso, e regras e direitos de
perfil saem em cascata.

FINALIDADE DE NEGÓCIO:
ACL (lista de controle de acesso) define quem lê, modifica ou administra cada
módulo. O recurso nasce sem regras, então a Reserva de Espaços continua aberta
a todo usuário autenticado; o SuperRoot (papel administrativo máximo) restringe
depois, se quiser, na tela de Controle de acesso.

CONTEXTO NO SISTEMA:
Tabela acl_recursos; rotas de app/api/routes/reserva_espacos.py e tela de ACL
(app/api/routes/acl.py). Aplicada com 'alembic upgrade head' (o instalador e a
atualização do sistema rodam esse comando).

Revision ID: f1c6a8d2e4b7
Revises: e9b3c5a7d1f2
Create Date: 2026-10-20

===============================================================================
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f1c6a8d2e4b7"
down_revision: str | Sequence[str] | None = "e9b3c5a7d1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "reserva-espacos"


def upgrade() -> None:
    """Cria o recurso sem regras (idempotente: se já foi criado à mão na tela de ACL, não duplica)."""
    conexao = op.get_bind()
    # Só insere se o slug ainda não existir: alguém pode ter criado o recurso pela tela
    if conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :slug"), {"slug": SLUG}) is None:
        conexao.execute(
            sa.text(
                "INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES (:nome, :slug, :descricao, '/reserva-espacos', true, :agora, :agora)"
            ),
            {"nome": "Reserva de Espaços", "slug": SLUG, "agora": datetime.now(UTC),
             "descricao": "Agenda e reserva de salas e anfiteatro. Sem regras nem perfis: todo usuário autenticado; os fiscais são cadastrados dentro do módulo."},
        )


def downgrade() -> None:
    """Remove o recurso (regras e direitos de perfil saem em cascata)."""
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :slug").bindparams(slug=SLUG))
