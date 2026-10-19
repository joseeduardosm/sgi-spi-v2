# Criado por José Eduardo Santana Martins
# Este arquivo serve para passar os direitos dos perfis de um nível por módulo para ações independentes (uma linha por ação).
"""perfis com ações independentes

Os direitos do perfil deixam de ser um nível hierárquico por módulo e passam a ser um conjunto de ações independentes:
a chave de `acl_perfis_direitos` ganha a coluna `nivel` (uma linha por ação). Os direitos antigos são expandidos para as ações
equivalentes (CONTROLE_TOTAL = as ações de todos os níveis até ele que o módulo oferece), então ninguém perde nem ganha acesso.

Revision ID: f4b0d8c6e2a5
Revises: e3a9c7b5d1f4
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

from app.services.acl_acoes import codigos_do_recurso

revision = "f4b0d8c6e2a5"
down_revision = "e3a9c7b5d1f4"
branch_labels = None
depends_on = None

ORDEM = {"LEITURA": 1, "MODIFICACAO": 2, "CONTROLE_TOTAL": 3}


def upgrade() -> None:
    conexao = op.get_bind()
    # Expande cada direito hierárquico nas ações do módulo até aquele nível (a ação que a porta do nível usa também entra)
    antigos = list(conexao.execute(sa.text(
        "SELECT d.perfil_id, d.recurso_id, d.nivel, r.slug FROM acl_perfis_direitos d JOIN acl_recursos r ON r.id = d.recurso_id")))
    op.drop_constraint("acl_perfis_direitos_pkey", "acl_perfis_direitos", type_="primary")
    op.create_primary_key("acl_perfis_direitos_pkey", "acl_perfis_direitos", ["perfil_id", "recurso_id", "nivel"])
    for perfil_id, recurso_id, nivel, slug in antigos:
        codigos = codigos_do_recurso(slug)
        # Ações até o nível antigo
        escolhidas = [c for c in codigos if ORDEM[c] <= ORDEM[nivel]]
        for codigo in escolhidas:
            if codigo == nivel:
                continue  # a linha original já existe
            conexao.execute(sa.text("INSERT INTO acl_perfis_direitos (perfil_id, recurso_id, nivel) VALUES (:p, :r, :n)"),
                            {"p": perfil_id, "r": recurso_id, "n": codigo})
        # Se o nível antigo não é uma ação do módulo, a linha original (nível) é trocada pelas ações
        if nivel not in codigos:
            conexao.execute(sa.text("DELETE FROM acl_perfis_direitos WHERE perfil_id = :p AND recurso_id = :r AND nivel = :n"),
                            {"p": perfil_id, "r": recurso_id, "n": nivel})


def downgrade() -> None:
    conexao = op.get_bind()
    # Volta a um nível por módulo: o maior das ações marcadas
    conexao.execute(sa.text(
        "DELETE FROM acl_perfis_direitos d USING acl_perfis_direitos o WHERE d.perfil_id = o.perfil_id AND d.recurso_id = o.recurso_id "
        "AND (CASE d.nivel WHEN 'LEITURA' THEN 1 WHEN 'MODIFICACAO' THEN 2 ELSE 3 END) < (CASE o.nivel WHEN 'LEITURA' THEN 1 WHEN 'MODIFICACAO' THEN 2 ELSE 3 END)"))
    op.drop_constraint("acl_perfis_direitos_pkey", "acl_perfis_direitos", type_="primary")
    op.create_primary_key("acl_perfis_direitos_pkey", "acl_perfis_direitos", ["perfil_id", "recurso_id"])
