# Criado por José Eduardo Santana Martins
# Este arquivo serve para cadastrar na ACL o recurso "RH", que passa a definir quem é o RH do sistema (antes embutido no código pelo nome do setor).

"""acl: recurso `rh` (quem é o RH vira parametrizável) e transferência dos poderes sobre setores

- Cria o recurso `rh` (LEITURA consulta a estrutura; MODIFICACAO gere setores e cargos; CONTROLE_TOTAL é o RH).
- Regra CONTROLE_TOTAL para o setor hoje configurado como CGP (`setor_cgp`) e todos os seus descendentes: o comportamento atual se mantém.
- Quem tinha CONTROLE_TOTAL em `setores` (usuários, setores e perfis) ganha MODIFICACAO em `rh`: os setores passam a ser gerenciados pelo RH.
  O recurso `setores` continua existindo só para consulta (LEITURA) nos demais módulos.

Revision ID: d5a1c7e3b9f2
Revises: c4f9a2d7e1b8
Create Date: 2026-10-22
"""
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "d5a1c7e3b9f2"
down_revision: str | Sequence[str] | None = "c4f9a2d7e1b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "rh"


def _descendentes(conexao, raizes: list[int]) -> list[int]:
    """Os setores informados e todos os seus descendentes."""
    todos = {i: p for i, p in conexao.execute(sa.text("SELECT id, setor_pai_id FROM setores")).all()}
    resultado, fila = set(raizes), list(raizes)
    while fila:
        pai = fila.pop()
        for i, p in todos.items():
            if p == pai and i not in resultado:
                resultado.add(i)
                fila.append(i)
    return sorted(resultado)


def _nova_regra(conexao, recurso_id: int, nivel: str, usuarios: list[int], setores: list[int], agora) -> None:
    regra_id = conexao.scalar(sa.text("INSERT INTO acl_regras (recurso_id, nivel, criado_em, atualizado_em) VALUES (:r, :n, :a, :a) RETURNING id"), {"r": recurso_id, "n": nivel, "a": agora})
    for u in usuarios:
        conexao.execute(sa.text("INSERT INTO acl_regras_usuarios (regra_id, usuario_id) VALUES (:r, :u)"), {"r": regra_id, "u": u})
    for s in setores:
        conexao.execute(sa.text("INSERT INTO acl_regras_setores (regra_id, setor_id) VALUES (:r, :s)"), {"r": regra_id, "s": s})


def upgrade() -> None:
    conexao = op.get_bind()
    agora = datetime.now(UTC)
    if conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :s"), {"s": SLUG}) is not None:
        return
    recurso_id = conexao.scalar(
        sa.text("INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES ('RH', :s, :d, '/rh', true, :a, :a) RETURNING id"),
        {"s": SLUG, "a": agora, "d": "Módulo RH: setores, cargos, organograma, cadastro das pessoas, férias e licenças. Quem tem Controle total é o RH do sistema."})

    # 1) O RH de hoje: o setor configurado como CGP e seus descendentes
    from app.core.configuracao import obter_configuracao

    nome = obter_configuracao().setor_cgp.strip().lower()
    raizes = [i for i, n in conexao.execute(sa.text("SELECT id, nome FROM setores")).all() if (n or "").strip().lower() == nome]
    if raizes:
        _nova_regra(conexao, recurso_id, "CONTROLE_TOTAL", [], _descendentes(conexao, raizes), agora)

    # 2) Quem gerenciava os setores (CONTROLE_TOTAL em `setores`) passa a gerir setores e cargos no RH
    setores_recurso = conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = 'setores'"))
    if setores_recurso is not None:
        usuarios = [u for (u,) in conexao.execute(sa.text(
            "SELECT DISTINCT ru.usuario_id FROM acl_regras r JOIN acl_regras_usuarios ru ON ru.regra_id = r.id WHERE r.recurso_id = :r AND r.nivel = 'CONTROLE_TOTAL'"), {"r": setores_recurso}).all()]
        setores = [s for (s,) in conexao.execute(sa.text(
            "SELECT DISTINCT rs.setor_id FROM acl_regras r JOIN acl_regras_setores rs ON rs.regra_id = r.id WHERE r.recurso_id = :r AND r.nivel = 'CONTROLE_TOTAL'"), {"r": setores_recurso}).all()]
        if usuarios or setores:
            _nova_regra(conexao, recurso_id, "MODIFICACAO", usuarios, setores, agora)
        for (perfil_id,) in conexao.execute(sa.text("SELECT DISTINCT perfil_id FROM acl_perfis_direitos WHERE recurso_id = :r AND nivel = 'CONTROLE_TOTAL'"), {"r": setores_recurso}).all():
            conexao.execute(sa.text("INSERT INTO acl_perfis_direitos (perfil_id, recurso_id, nivel) VALUES (:p, :r, 'MODIFICACAO')"), {"p": perfil_id, "r": recurso_id})


def downgrade() -> None:
    """Remove o recurso (regras e direitos de perfil saem em cascata); o RH volta a ser o setor configurado em `setor_cgp`."""
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :s").bindparams(s=SLUG))
