# Criado por José Eduardo Santana Martins
# Este arquivo serve para dar a cada equipamento de rede a sua função na topologia (core primário/secundário, distribuição, acesso),
# o tipo "access point" e o resultado do teste de ping no IP de gerência.

"""rede: função do equipamento na topologia, access point e ping

- `rede_equipamentos.tipo` aceita `access_point`;
- `rede_equipamentos.funcao`: `core_primario`, `core_secundario`, `distribuicao` ou `acesso` (vazio nos que já existem: a tela pede na próxima edição);
- `ping_situacao` (`no_ar`/`fora`), `ping_falhas` (falhas seguidas), `ping_verificado_em` e `ping_mudou_em`;
- `rede_parametros` (chave/valor), com o intervalo entre as rodadas de ping (`ping_intervalo_min`).

Revision ID: e2a4c6e8b0d1
Revises: d0f2b4c6e8a9
Create Date: 2026-11-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e2a4c6e8b0d1"
down_revision: str | Sequence[str] | None = "d0f2b4c6e8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPOS_ANTIGOS = "'switch', 'patch_panel', 'roteador', 'outro'"
TIPOS = "'switch', 'patch_panel', 'roteador', 'access_point', 'outro'"


def upgrade() -> None:
    """Novos campos vazios: nada muda nos equipamentos que já existem."""
    with op.batch_alter_table("rede_equipamentos") as tabela:
        tabela.drop_constraint("ck_rede_equipamentos_tipo", type_="check")
        tabela.create_check_constraint("ck_rede_equipamentos_tipo", f"tipo IN ({TIPOS})")
        tabela.add_column(sa.Column("funcao", sa.String(16)))
        tabela.add_column(sa.Column("ping_situacao", sa.String(6)))
        tabela.add_column(sa.Column("ping_falhas", sa.Integer, nullable=False, server_default="0"))
        tabela.add_column(sa.Column("ping_verificado_em", sa.DateTime(timezone=True)))
        tabela.add_column(sa.Column("ping_mudou_em", sa.DateTime(timezone=True)))
        tabela.create_check_constraint("ck_rede_equipamentos_funcao",
                                       "funcao IS NULL OR funcao IN ('core_primario', 'core_secundario', 'distribuicao', 'acesso')")
        tabela.create_check_constraint("ck_rede_equipamentos_ping", "ping_situacao IS NULL OR ping_situacao IN ('no_ar', 'fora')")
    op.create_table("rede_parametros", sa.Column("chave", sa.String(60), primary_key=True), sa.Column("valor", sa.String(200), nullable=False),
                    sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade() -> None:
    """Tira os campos; access point volta a "outro"."""
    op.drop_table("rede_parametros")
    op.execute("UPDATE rede_equipamentos SET tipo = 'outro' WHERE tipo = 'access_point'")
    with op.batch_alter_table("rede_equipamentos") as tabela:
        tabela.drop_constraint("ck_rede_equipamentos_ping", type_="check")
        tabela.drop_constraint("ck_rede_equipamentos_funcao", type_="check")
        for coluna in ("ping_mudou_em", "ping_verificado_em", "ping_falhas", "ping_situacao", "funcao"):
            tabela.drop_column(coluna)
        tabela.drop_constraint("ck_rede_equipamentos_tipo", type_="check")
        tabela.create_check_constraint("ck_rede_equipamentos_tipo", f"tipo IN ({TIPOS_ANTIGOS})")
