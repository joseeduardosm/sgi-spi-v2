# Criado por José Eduardo Santana Martins
# Este arquivo serve para dar nomes de verdade aos perfis de acesso criados pela migração das regras antigas.
"""nomes dos perfis migrados

Dá nomes de verdade aos perfis criados pela migração d2f8b6a4c0e1 ("Migrado N: ..."), a partir do que cada um libera.

Revision ID: e3a9c7b5d1f4
Revises: d2f8b6a4c0e1
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

revision = "e3a9c7b5d1f4"
down_revision = "d2f8b6a4c0e1"
branch_labels = None
depends_on = None

# Nome antigo (prefixo "Migrado N:") → nome novo, com descrição
NOMES = {
    "Migrado 1:": ("Administrador do sistema", "Importações, atalhos, documentação da API, SLA, contratações e notificações para setores."),
    "Migrado 2:": ("Editor-chefe de Notícias", "Controle total do módulo Notícias."),
    "Migrado 3:": ("Editor de Notícias", "Cria e edita notícias (Modificação)."),
    "Migrado 4:": ("Gestor de Patrimônio", "Controle total do módulo Patrimônio."),
    "Migrado 5:": ("Gestor de Contratos", "Controle total do módulo Contratos."),
    "Migrado 6:": ("Notificações para setores", "Envia notificações para setores inteiros."),
}


def upgrade() -> None:
    conexao = op.get_bind()
    for prefixo, (nome, descricao) in NOMES.items():
        # Só renomeia o que ainda tem o nome gerado e quando o nome novo está livre
        conexao.execute(
            sa.text(
                "UPDATE acl_perfis SET nome = :nome, descricao = :descricao WHERE nome LIKE :prefixo "
                "AND NOT EXISTS (SELECT 1 FROM acl_perfis WHERE lower(nome) = lower(:nome))"
            ),
            {"nome": nome, "descricao": descricao, "prefixo": prefixo + "%"},
        )


def downgrade() -> None:
    # Os nomes antigos eram gerados a partir dos usuários; não há como reconstruí-los, então o downgrade só mantém os nomes novos.
    pass
