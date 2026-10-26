# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a tabela da configuração do menu lateral e levar para ela os atalhos fixos que já existem (categorias viram grupos; atalhos, links).

"""menu: configuração do menu lateral (ordem, grupos, links e itens ocultos)

- Cria `menu_configuracao` (linha única com a lista de nós em JSON).
- Se já há atalhos fixos ativos, semeia a configuração: o item Início e o grupo Módulos primeiro, depois cada categoria ativa como grupo e cada atalho ativo como link;
  o resto do menu entra no fim, na ordem padrão do código. As tabelas `atalhos_*` continuam existindo (sem uso pelo menu).

Revision ID: b2d6f0a4c8e1
Revises: a1c5e9b3d7f4
Create Date: 2026-10-25
"""
from collections.abc import Sequence
from datetime import UTC, datetime
import json

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b2d6f0a4c8e1"
down_revision: str | Sequence[str] | None = "f9a5b1c7d3e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "menu_configuracao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("itens", sa.JSON(), nullable=False),
        sa.Column("atualizado_por_nome", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    conexao = op.get_bind()
    categorias = conexao.execute(sa.text("SELECT id, nome FROM atalhos_categorias WHERE ativo ORDER BY ordem, lower(nome)")).all()
    nos: list[dict] = []
    for categoria_id, nome in categorias:
        atalhos = conexao.execute(
            sa.text("SELECT id, titulo, url, nova_aba FROM atalhos_fixos WHERE ativo AND categoria_id = :c ORDER BY ordem, id"), {"c": categoria_id}).all()
        if not atalhos:
            continue
        grupo = f"g-cat-{categoria_id}"
        nos.append({"id": grupo, "tipo": "grupo", "rotulo": nome[:80]})
        for atalho_id, titulo, url, nova_aba in atalhos:
            no = {"id": f"l-{atalho_id}", "tipo": "link", "rotulo": titulo[:80], "pai_id": grupo, "url": url}
            if nova_aba is not None:
                no["nova_aba"] = bool(nova_aba)
            nos.append(no)
    if not nos:
        return
    itens = [{"id": "inicio", "tipo": "modulo"}, {"id": "modulos", "tipo": "modulo"}, *nos]
    conexao.execute(sa.text("INSERT INTO menu_configuracao (id, itens, atualizado_por_nome, atualizado_em) VALUES (1, CAST(:i AS JSON), 'Migração dos atalhos fixos', :a)"),
                    {"i": json.dumps(itens, ensure_ascii=False), "a": datetime.now(UTC)})


def downgrade() -> None:
    op.drop_table("menu_configuracao")
