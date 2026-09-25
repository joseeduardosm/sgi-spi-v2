# Criado por José Eduardo Santana Martins
# Este arquivo serve para renomear tabelas, colunas e restrições do banco para o português.
"""nomes de tabelas, colunas, índices e constraints em português

Renomeia (sem recriar) para preservar os dados existentes.

Revision ID: a1c3e5f7b9d2
Revises: 7fb1ed802b9e
Create Date: 2026-09-23 21:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3e5f7b9d2"
down_revision: str | Sequence[str] | None = "7fb1ed802b9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELAS = {
    "users": "usuarios",
    "ldap_directories": "diretorios_ldap",
    "audit_log": "auditoria",
    "sectors": "setores",
    "sector_members": "membros_setor",
    "acl_resources": "acl_recursos",
    "acl_rules": "acl_regras",
    "acl_rule_users": "acl_regras_usuarios",
    "acl_rule_sectors": "acl_regras_setores",
}

# Colunas por tabela (nome já novo da tabela): antigo -> novo
COLUNAS = {
    "usuarios": {
        "username": "login",
        "password_hash": "hash_senha",
        "is_active": "ativo",
        "is_superuser": "superusuario",
        "origin": "origem",
        "directory_id": "diretorio_id",
        "external_id": "id_externo",
        "distinguished_name": "dn",
        "full_name": "nome_completo",
        "extension": "ramal",
        "mobile": "celular",
        "job_title": "cargo",
        "department": "departamento",
        "floor": "andar",
        "building": "predio",
        "birth_date": "data_nascimento",
        "manager_id": "gestor_id",
        "profile_reviewed_at": "perfil_revisado_em",
        "last_login_at": "ultimo_acesso_em",
        "created_at": "criado_em",
        "updated_at": "atualizado_em",
    },
    "diretorios_ldap": {
        "name": "nome",
        "host": "servidor",
        "port": "porta",
        "use_ssl": "usar_ssl",
        "bind_password_encrypted": "senha_bind_cifrada",
        "is_active": "ativo",
        "last_test_at": "ultimo_teste_em",
        "last_test_ok": "ultimo_teste_ok",
        "last_latency_ms": "ultima_latencia_ms",
        "last_error": "ultimo_erro",
        "last_sync_at": "ultima_sincronizacao_em",
        "last_sync_ok": "ultima_sincronizacao_ok",
        "last_sync_message": "ultima_sincronizacao_mensagem",
        "created_at": "criado_em",
        "updated_at": "atualizado_em",
    },
    "auditoria": {"at": "ocorrido_em", "actor": "autor", "action": "acao", "target": "alvo", "details": "detalhes"},
    "setores": {
        "name": "nome",
        "parent_id": "setor_pai_id",
        "leader_id": "lider_id",
        "is_systemic": "sistemico",
        "is_active": "ativo",
        "created_at": "criado_em",
        "updated_at": "atualizado_em",
    },
    "membros_setor": {"sector_id": "setor_id", "user_id": "usuario_id", "created_at": "criado_em"},
    "acl_recursos": {
        "name": "nome",
        "description": "descricao",
        "is_active": "ativo",
        "created_at": "criado_em",
        "updated_at": "atualizado_em",
    },
    "acl_regras": {"resource_id": "recurso_id", "level": "nivel", "created_at": "criado_em", "updated_at": "atualizado_em"},
    "acl_regras_usuarios": {"rule_id": "regra_id", "user_id": "usuario_id"},
    "acl_regras_setores": {"rule_id": "regra_id", "sector_id": "setor_id"},
}

INDICES = {
    "ix_audit_log_action": "ix_auditoria_acao",
    "ix_audit_log_at": "ix_auditoria_ocorrido_em",
    "ux_ldap_directories_single_active": "ux_diretorios_ldap_unico_ativo",
    "ix_users_directory_id": "ix_usuarios_diretorio_id",
    "ix_users_external_id": "ix_usuarios_id_externo",
    "ux_users_username_lower": "ux_usuarios_login_minusculo",
    "ix_sectors_parent_id": "ix_setores_setor_pai_id",
    "ux_sectors_name_lower": "ux_setores_nome_minusculo",
    "ix_sector_members_user_id": "ix_membros_setor_usuario_id",
    "ux_acl_resources_name_lower": "ux_acl_recursos_nome_minusculo",
    "ix_acl_rules_resource_id": "ix_acl_regras_recurso_id",
    "ix_acl_rule_users_user_id": "ix_acl_regras_usuarios_usuario_id",
    "ix_acl_rule_sectors_sector_id": "ix_acl_regras_setores_setor_id",
}

SEQUENCIAS = {
    "users_id_seq": "usuarios_id_seq",
    "audit_log_id_seq": "auditoria_id_seq",
    "sectors_id_seq": "setores_id_seq",
    "acl_resources_id_seq": "acl_recursos_id_seq",
    "acl_rules_id_seq": "acl_regras_id_seq",
}


def _renomear_constraints(tabelas: list[str]) -> None:
    """Dá às chaves primárias, estrangeiras e únicas o nome padrão do PostgreSQL para as tabelas/colunas atuais."""
    conexao = op.get_bind()
    for tabela in tabelas:
        linhas = conexao.execute(
            sa.text(
                """
                SELECT c.conname, c.contype,
                       (SELECT string_agg(a.attname, '_' ORDER BY k.ordem)
                          FROM unnest(c.conkey) WITH ORDINALITY AS k(num, ordem)
                          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.num) AS colunas
                  FROM pg_constraint c
                 WHERE c.conrelid = CAST(:tabela AS regclass) AND c.contype IN ('p', 'f', 'u')
                """
            ),
            {"tabela": tabela},
        ).all()
        for nome_atual, tipo, colunas in linhas:
            novo = {"p": f"{tabela}_pkey", "f": f"{tabela}_{colunas}_fkey", "u": f"{tabela}_{colunas}_key"}[tipo]
            if novo != nome_atual:
                op.execute(f'ALTER TABLE "{tabela}" RENAME CONSTRAINT "{nome_atual}" TO "{novo}"')


def upgrade() -> None:
    for antigo, novo in TABELAS.items():
        op.rename_table(antigo, novo)
    for tabela, colunas in COLUNAS.items():
        for antiga, nova in colunas.items():
            op.alter_column(tabela, antiga, new_column_name=nova)
    for antigo, novo in INDICES.items():
        op.execute(f'ALTER INDEX "{antigo}" RENAME TO "{novo}"')
    for antigo, novo in SEQUENCIAS.items():
        op.execute(f'ALTER SEQUENCE "{antigo}" RENAME TO "{novo}"')
    _renomear_constraints(list(TABELAS.values()))


def downgrade() -> None:
    for antigo, novo in SEQUENCIAS.items():
        op.execute(f'ALTER SEQUENCE "{novo}" RENAME TO "{antigo}"')
    for antigo, novo in INDICES.items():
        op.execute(f'ALTER INDEX "{novo}" RENAME TO "{antigo}"')
    for tabela, colunas in COLUNAS.items():
        for antiga, nova in colunas.items():
            op.alter_column(tabela, nova, new_column_name=antiga)
    for antigo, novo in TABELAS.items():
        op.rename_table(novo, antigo)
    _renomear_constraints(list(TABELAS.keys()))
