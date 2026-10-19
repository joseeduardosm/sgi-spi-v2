# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar os perfis de acesso (ACL por perfil), a auditoria da personificação e migrar as regras atuais para perfis.
"""acl: perfis de acesso e personificação

- `acl_perfis`, `acl_perfis_direitos` (perfil × recurso × nível) e `usuarios_perfis` (perfis do usuário e o padrão).
- `auditoria.personificado_por_id`: SuperRoot que agiu personificando outro usuário.
- **Dados:** as regras existentes que citam o **mesmo conjunto de usuários** viram um perfil "Migrado N: …" (um por grupo), atribuído a esses usuários.
  As regras por setor e as regras diretas **continuam como estão** (nada é apagado), então ninguém perde nem ganha acesso por causa da migração.

Revision ID: d2f8b6a4c0e1
Revises: c1e7a3d9f5b2
Create Date: 2026-10-16 14:00:00
"""
import logging
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd2f8b6a4c0e1'
down_revision: Union[str, Sequence[str], None] = 'c1e7a3d9f5b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")
ORDEM = {"LEITURA": 1, "MODIFICACAO": 2, "CONTROLE_TOTAL": 3}


def upgrade() -> None:
    op.create_table(
        'acl_perfis',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=False, server_default=''),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ux_acl_perfis_nome_minusculo', 'acl_perfis', [sa.literal_column('lower(nome)')], unique=True)
    op.create_table(
        'acl_perfis_direitos',
        sa.Column('perfil_id', sa.Integer(), sa.ForeignKey('acl_perfis.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('recurso_id', sa.Integer(), sa.ForeignKey('acl_recursos.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('nivel', sa.String(length=20), nullable=False),
    )
    op.create_index('ix_acl_perfis_direitos_recurso_id', 'acl_perfis_direitos', ['recurso_id'])
    op.create_table(
        'usuarios_perfis',
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('perfil_id', sa.Integer(), sa.ForeignKey('acl_perfis.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('padrao', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index('ix_usuarios_perfis_perfil_id', 'usuarios_perfis', ['perfil_id'])
    op.add_column('auditoria', sa.Column('personificado_por_id', sa.Integer(), nullable=True))
    _migrar_regras()


def _migrar_regras() -> None:
    """Um perfil por grupo de regras com o mesmo conjunto de usuários."""
    conexao = op.get_bind()
    regras = {r.id: (r.recurso_id, r.nivel) for r in conexao.execute(sa.text("SELECT id, recurso_id, nivel FROM acl_regras"))}
    usuarios_da_regra: dict[int, set[int]] = {}
    for regra_id, usuario_id in conexao.execute(sa.text("SELECT regra_id, usuario_id FROM acl_regras_usuarios")):
        usuarios_da_regra.setdefault(regra_id, set()).add(usuario_id)
    grupos: dict[frozenset[int], list[int]] = {}
    for regra_id, usuarios in usuarios_da_regra.items():
        if regra_id in regras and usuarios:
            grupos.setdefault(frozenset(usuarios), []).append(regra_id)
    nomes = {u.id: (u.nome_completo or u.login) for u in conexao.execute(sa.text("SELECT id, nome_completo, login FROM usuarios"))}
    agora = datetime.now(UTC)
    com_padrao: set[int] = set()
    for numero, (usuarios, regras_do_grupo) in enumerate(sorted(grupos.items(), key=lambda g: sorted(g[0])), start=1):
        ordenados = sorted(usuarios, key=lambda i: nomes.get(i, ""))
        resumo = ", ".join(nomes.get(i, str(i)) for i in ordenados[:2]) + (f" +{len(ordenados) - 2}" if len(ordenados) > 2 else "")
        nome = f"Migrado {numero}: {resumo}"[:100]
        perfil_id = conexao.scalar(sa.text(
            "INSERT INTO acl_perfis (nome, descricao, ativo, criado_em, atualizado_em) VALUES (:nome, :descricao, true, :agora, :agora) RETURNING id"),
            {"nome": nome, "descricao": "Criado automaticamente a partir das regras de acesso que citavam exatamente estes usuários. Revise o nome e as permissões.", "agora": agora})
        direitos: dict[int, str] = {}
        for regra_id in regras_do_grupo:
            recurso_id, nivel = regras[regra_id]
            if ORDEM.get(nivel, 0) > ORDEM.get(direitos.get(recurso_id, ""), 0):
                direitos[recurso_id] = nivel
        for recurso_id, nivel in direitos.items():
            conexao.execute(sa.text("INSERT INTO acl_perfis_direitos (perfil_id, recurso_id, nivel) VALUES (:p, :r, :n)"), {"p": perfil_id, "r": recurso_id, "n": nivel})
        for usuario_id in ordenados:
            conexao.execute(sa.text("INSERT INTO usuarios_perfis (usuario_id, perfil_id, padrao) VALUES (:u, :p, :padrao)"),
                            {"u": usuario_id, "p": perfil_id, "padrao": usuario_id not in com_padrao})
            com_padrao.add(usuario_id)
        log.info("Perfil migrado %s: %s recurso(s), %s usuário(s).", nome, len(direitos), len(ordenados))


def downgrade() -> None:
    op.drop_column('auditoria', 'personificado_por_id')
    op.drop_index('ix_usuarios_perfis_perfil_id', table_name='usuarios_perfis')
    op.drop_table('usuarios_perfis')
    op.drop_index('ix_acl_perfis_direitos_recurso_id', table_name='acl_perfis_direitos')
    op.drop_table('acl_perfis_direitos')
    op.drop_index('ux_acl_perfis_nome_minusculo', table_name='acl_perfis')
    op.drop_table('acl_perfis')
