# Criado por José Eduardo Santana Martins
# Este arquivo serve para renomear a Mensageria para Notificações (tabelas, colunas, constraints, índices, recurso ACL e auditoria), sem perder histórico.
"""mensageria vira notificacoes

Só renomeia: nenhuma tabela é recriada e nenhuma linha é copiada. Os nomes explícitos de PK, FK, UNIQUE, CHECK e índices
(que o PostgreSQL guarda com o nome antigo) são trocados junto, para o banco refletir o modelo.

Revision ID: d4e8a1c6b2f7
Revises: c3badbe90657
Create Date: 2026-10-12 03:00:00
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e8a1c6b2f7'
down_revision: Union[str, Sequence[str], None] = 'c3badbe90657'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (nome antigo, nome novo) das constraints de cada tabela, na tabela já com o nome novo
CONSTRAINTS = {
    'notificacoes': [
        ('mensagens_pkey', 'notificacoes_pkey'),
        ('mensagens_autor_id_fkey', 'notificacoes_autor_id_fkey'),
        ('mensagens_contrato_id_fkey', 'notificacoes_contrato_id_fkey'),
        ('ck_mensagens_prioridade', 'ck_notificacoes_prioridade'),
        ('ck_mensagens_categoria', 'ck_notificacoes_categoria'),
        ('ck_mensagens_origem', 'ck_notificacoes_origem'),
    ],
    'notificacoes_entregas': [
        ('mensagens_entregas_pkey', 'notificacoes_entregas_pkey'),
        ('mensagens_entregas_destinatario_id_fkey', 'notificacoes_entregas_destinatario_id_fkey'),
        ('mensagens_entregas_mensagem_id_fkey', 'notificacoes_entregas_notificacao_id_fkey'),
        ('uq_mensagens_entregas_mensagem_destinatario', 'uq_notificacoes_entregas_notificacao_destinatario'),
    ],
    'notificacoes_envios_changelog': [
        ('mensageria_envios_changelog_pkey', 'notificacoes_envios_changelog_pkey'),
        ('mensageria_envios_changelog_enviado_por_id_fkey', 'notificacoes_envios_changelog_enviado_por_id_fkey'),
        ('ck_mensageria_envios_changelog_destino', 'ck_notificacoes_envios_changelog_destino'),
    ],
}
# Índices avulsos (os das PKs e do UNIQUE acompanham a constraint ao renomeá-la)
INDICES = [
    ('ix_mensagens_autor_id', 'ix_notificacoes_autor_id'),
    ('ix_mensagens_chave', 'ix_notificacoes_chave'),
    ('ix_mensagens_contrato_id', 'ix_notificacoes_contrato_id'),
    ('ix_mensagens_entregas_destinatario_ciente', 'ix_notificacoes_entregas_destinatario_ciente'),
    ('ix_mensagens_entregas_mensagem_id', 'ix_notificacoes_entregas_notificacao_id'),
]


def _renomear(sentido_novo: bool) -> None:
    """Aplica (ou desfaz) todos os nomes. `sentido_novo=False` inverte cada par."""
    par = (lambda a, b: (a, b)) if sentido_novo else (lambda a, b: (b, a))
    tabelas = [('mensagens', 'notificacoes'), ('mensagens_entregas', 'notificacoes_entregas'), ('mensageria_envios_changelog', 'notificacoes_envios_changelog')]
    if sentido_novo:
        for antiga, nova in tabelas:
            op.rename_table(antiga, nova)
        op.alter_column('notificacoes_entregas', 'mensagem_id', new_column_name='notificacao_id')
    for tabela, pares in CONSTRAINTS.items():
        for a, b in pares:
            antigo, novo = par(a, b)
            op.execute(f'ALTER TABLE {tabela} RENAME CONSTRAINT {antigo} TO {novo}')
    for a, b in INDICES:
        antigo, novo = par(a, b)
        op.execute(f'ALTER INDEX {antigo} RENAME TO {novo}')
    if not sentido_novo:
        op.alter_column('notificacoes_entregas', 'notificacao_id', new_column_name='mensagem_id')
        for antiga, nova in tabelas:
            op.rename_table(nova, antiga)


def upgrade() -> None:
    """Tabelas, coluna, constraints e índices; depois o recurso ACL e as ações da auditoria."""
    _renomear(True)
    # Recurso ACL: as regras apontam por id e ficam como estão
    op.execute("UPDATE acl_recursos SET slug = 'notificacoes-setores', nome = 'Notificações: envio para setores', "
               "descricao = 'Enviar notificações para setores inteiros na caixa de notificações (exige CONTROLE_TOTAL).', url_base = '/notificacoes' "
               "WHERE slug = 'mensageria-setores'")
    # Histórico da auditoria com os nomes novos (mensagem.* -> notificacao.*, mensageria.changelog -> notificacoes.changelog)
    op.execute("UPDATE auditoria SET acao = 'notificacao.' || substr(acao, length('mensagem.') + 1) WHERE acao LIKE 'mensagem.%'")
    op.execute("UPDATE auditoria SET acao = 'notificacoes.changelog' WHERE acao = 'mensageria.changelog'")
    op.execute("UPDATE auditoria SET alvo_tipo = 'notificacao' WHERE alvo_tipo = 'mensagem'")


def downgrade() -> None:
    """Desfaz tudo, na ordem inversa."""
    op.execute("UPDATE auditoria SET alvo_tipo = 'mensagem' WHERE alvo_tipo = 'notificacao'")
    op.execute("UPDATE auditoria SET acao = 'mensageria.changelog' WHERE acao = 'notificacoes.changelog'")
    op.execute("UPDATE auditoria SET acao = 'mensagem.' || substr(acao, length('notificacao.') + 1) WHERE acao LIKE 'notificacao.%'")
    op.execute("UPDATE acl_recursos SET slug = 'mensageria-setores', nome = 'Mensageria: envio para setores', "
               "descricao = 'Enviar mensagens para setores inteiros na caixa de mensagens (exige CONTROLE_TOTAL).', url_base = '/mensagens' "
               "WHERE slug = 'notificacoes-setores'")
    _renomear(False)
