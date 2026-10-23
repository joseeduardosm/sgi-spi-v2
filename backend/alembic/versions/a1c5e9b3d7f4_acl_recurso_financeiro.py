# Criado por José Eduardo Santana Martins
# Este arquivo serve para cadastrar na ACL o recurso "Financeiro", que passa a definir quem confere a retenção de tributos (antes embutido no código pelo nome do setor).

"""acl: recurso `financeiro` (quem é o Financeiro dos contratos vira parametrizável)

- Cria o recurso `financeiro` (MODIFICACAO ou mais = é o Financeiro: confere a retenção e recebe os avisos).
- Regra MODIFICACAO para o setor hoje configurado em `setor_financeiro` e todos os seus descendentes, mais quem o tem como Departamento no perfil:
  o comportamento atual se mantém.

Revision ID: a1c5e9b3d7f4
Revises: e8f4a0b6c2d5
Create Date: 2026-10-23
"""
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "a1c5e9b3d7f4"
down_revision: str | Sequence[str] | None = "e8f4a0b6c2d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "financeiro"


def upgrade() -> None:
    conexao = op.get_bind()
    agora = datetime.now(UTC)
    if conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :s"), {"s": SLUG}) is not None:
        return
    recurso_id = conexao.scalar(
        sa.text("INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES ('Financeiro', :s, :d, '/contratos', true, :a, :a) RETURNING id"),
        {"s": SLUG, "a": agora, "d": "Quem é o Financeiro dos contratos: confere a retenção de tributos das notas fiscais e recebe os avisos. Quem tem Modificação ou mais é o Financeiro."})

    from app.core.configuracao import obter_configuracao

    nome = obter_configuracao().setor_financeiro.strip().lower()
    setores = {i: (n or "", p) for i, n, p in conexao.execute(sa.text("SELECT id, nome, setor_pai_id FROM setores")).all()}
    raizes = [i for i, (n, _) in setores.items() if n.strip().lower() == nome]
    alvo, fila = set(raizes), list(raizes)
    while fila:
        pai = fila.pop()
        for i, (_, p) in setores.items():
            if p == pai and i not in alvo:
                alvo.add(i)
                fila.append(i)
    if not alvo:
        return
    # Quem era Financeiro só pelo Departamento do perfil (sem ser membro do setor) entra como usuário direto
    nomes = [setores[i][0].strip().lower() for i in alvo]
    usuarios = [u for u, d in conexao.execute(sa.text("SELECT id, departamento FROM usuarios WHERE ativo")).all() if (d or "").strip().lower() in nomes]
    regra_id = conexao.scalar(sa.text("INSERT INTO acl_regras (recurso_id, nivel, criado_em, atualizado_em) VALUES (:r, 'MODIFICACAO', :a, :a) RETURNING id"), {"r": recurso_id, "a": agora})
    for s in sorted(alvo):
        conexao.execute(sa.text("INSERT INTO acl_regras_setores (regra_id, setor_id) VALUES (:r, :s)"), {"r": regra_id, "s": s})
    for u in usuarios:
        conexao.execute(sa.text("INSERT INTO acl_regras_usuarios (regra_id, usuario_id) VALUES (:r, :u)"), {"r": regra_id, "u": u})


def downgrade() -> None:
    """Remove o recurso (regras e direitos de perfil saem em cascata); o Financeiro volta a ser o setor configurado em `setor_financeiro`."""
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :s").bindparams(s=SLUG))
