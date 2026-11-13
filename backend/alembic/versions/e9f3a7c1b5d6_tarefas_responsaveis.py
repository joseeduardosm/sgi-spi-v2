"""
===============================================================================
ARQUIVO: e9f3a7c1b5d6_tarefas_responsaveis.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que transforma os participantes das tarefas em responsáveis:
renomeia a tabela tarefas_participantes para tarefas_responsaveis e inclui na
lista o responsável principal de cada tarefa.

RESUMO TÉCNICO:
O upgrade renomeia a tabela, a restrição única, os índices e a sequência com
op.rename_table e ALTER ... RENAME, e depois insere em tarefas_responsaveis o
responsavel_id de cada tarefa que ainda não estava na lista (INSERT ... SELECT
com NOT EXISTS). O downgrade volta os nomes antigos, mas mantém as linhas
incluídas.

FINALIDADE DE NEGÓCIO:
No módulo Tarefas, uma tarefa pode ter vários responsáveis que respondem
igualmente pela entrega. Tarefas antigas (migradas) tinham o responsável
principal fora da lista e deixariam de aparecer para ele.

CONTEXTO NO SISTEMA:
Tabelas tarefas, tarefas_responsaveis e usuarios; modelo em
app/models/tarefas.py e serviço app/services/tarefas/servico_tarefas.py.
Aplicada com 'alembic upgrade head' (o instalador e a atualização do sistema
rodam esse comando).

Revision ID: e9f3a7c1b5d6
Revises: d8e2f6b0a4c5
Create Date: 2026-10-07 14:00:00

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração para o Alembic: "revision" é o id desta migração e
# "down_revision" a anterior na cadeia (o Alembic aplica na ordem dessa corrente).
revision: str = "e9f3a7c1b5d6"
down_revision: str | Sequence[str] | None = "d8e2f6b0a4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Todos os participantes passam a ser responsáveis (mesma tabela, renomeada); o responsável principal de cada tarefa também entra na lista."""
    # op.* são as operações de esquema do Alembic (renomear tabela, criar coluna...);
    # op.execute roda um SQL cru. Renomeia a tabela e, em seguida, a restrição, os
    # índices e a sequência dela, para os nomes continuarem coerentes com a tabela nova.
    op.rename_table("tarefas_participantes", "tarefas_responsaveis")
    op.execute("ALTER TABLE tarefas_responsaveis RENAME CONSTRAINT uq_tarefas_participantes TO uq_tarefas_responsaveis")
    op.execute("ALTER INDEX IF EXISTS ix_tarefas_participantes_tarefa_id RENAME TO ix_tarefas_responsaveis_tarefa_id")
    op.execute("ALTER INDEX IF EXISTS ix_tarefas_participantes_usuario_id RENAME TO ix_tarefas_responsaveis_usuario_id")
    op.execute("ALTER SEQUENCE IF EXISTS tarefas_participantes_id_seq RENAME TO tarefas_responsaveis_id_seq")
    # Tarefas antigas (migradas) podem ter o responsável principal fora da lista de participantes
    op.execute(
        "INSERT INTO tarefas_responsaveis (tarefa_id, usuario_id) "
        "SELECT t.id, t.responsavel_id FROM tarefas t WHERE t.responsavel_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM tarefas_responsaveis r WHERE r.tarefa_id = t.id AND r.usuario_id = t.responsavel_id)"
    )


def downgrade() -> None:
    """Volta o nome antigo da tabela (os responsáveis incluídos continuam como participantes)."""
    # Ordem inversa do upgrade: primeiro sequência e índices, por fim a tabela
    op.execute("ALTER SEQUENCE IF EXISTS tarefas_responsaveis_id_seq RENAME TO tarefas_participantes_id_seq")
    op.execute("ALTER INDEX IF EXISTS ix_tarefas_responsaveis_usuario_id RENAME TO ix_tarefas_participantes_usuario_id")
    op.execute("ALTER INDEX IF EXISTS ix_tarefas_responsaveis_tarefa_id RENAME TO ix_tarefas_participantes_tarefa_id")
    op.execute("ALTER TABLE tarefas_responsaveis RENAME CONSTRAINT uq_tarefas_responsaveis TO uq_tarefas_participantes")
    op.rename_table("tarefas_responsaveis", "tarefas_participantes")
