"""
===============================================================================
ARQUIVO: f7a1c3e5b9d2_rede_lados_do_patch_panel.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Preparar o banco da Rede para os dois lados da porta do patch panel (fundo e
frente), para a descrição gerada pelo sistema e para a observação da porta.

RESUMO TÉCNICO:
- `rede_conexoes.lado_a` e `lado_b` ("fundo" ou "frente", vazios fora do patch
  panel), com CHECK; os índices únicos por porta passam a ser por porta e lado.
- Ligações que já existiam em porta de patch panel ganham um lado pela
  convenção mais comum: cabo para outra porta (switch) = frente; bem ou
  descrição (telefone, computador) = fundo.
- `rede_portas.observacao` (texto livre opcional) e o padrão da descrição
  passa a ser "Desligado".

FINALIDADE DE NEGÓCIO:
A porta do patch panel tem um cabo na frente e outro no fundo; sem guardar o
lado, o caminho até o core misturava fios diferentes do mesmo patch panel.

CONTEXTO NO SISTEMA:
Modelos em app/models/rede.py; regras em app/services/rede/servico.py.

Revision ID: f7a1c3e5b9d2
Revises: a3c5e7f9b1d4
Create Date: 2026-11-12
===============================================================================
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f7a1c3e5b9d2"
down_revision: str | Sequence[str] | None = "a3c5e7f9b1d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rede_conexoes", sa.Column("lado_a", sa.String(6), nullable=True))
    op.add_column("rede_conexoes", sa.Column("lado_b", sa.String(6), nullable=True))
    op.add_column("rede_portas", sa.Column("observacao", sa.Text(), nullable=False, server_default=""))
    op.alter_column("rede_portas", "descricao", server_default="Desligado")
    # Convenção para as ligações antigas em porta de patch panel: com outra porta = frente; com bem ou descrição = fundo
    eh_patch = ("(SELECT e.tipo FROM rede_portas p JOIN rede_equipamentos e ON e.id = p.equipamento_id WHERE p.id = {col}) = 'patch_panel'")
    op.execute(f"UPDATE rede_conexoes SET lado_a = CASE WHEN porta_b_id IS NULL THEN 'fundo' ELSE 'frente' END WHERE {eh_patch.format(col='porta_a_id')}")
    op.execute(f"UPDATE rede_conexoes SET lado_b = 'frente' WHERE porta_b_id IS NOT NULL AND {eh_patch.format(col='porta_b_id')}")
    with op.batch_alter_table("rede_conexoes") as tabela:
        tabela.create_check_constraint("ck_rede_conexoes_lado_a", "lado_a IS NULL OR lado_a IN ('fundo', 'frente')")
        tabela.create_check_constraint("ck_rede_conexoes_lado_b", "lado_b IS NULL OR lado_b IN ('fundo', 'frente')")
    # Os índices únicos passam a valer por porta e lado (a frente e o fundo da mesma porta são ligações diferentes)
    op.drop_index("ux_rede_conexoes_a", table_name="rede_conexoes")
    op.drop_index("ux_rede_conexoes_b", table_name="rede_conexoes")
    op.create_index("ux_rede_conexoes_a", "rede_conexoes", ["porta_a_id", sa.text("coalesce(lado_a, '')")], unique=True)
    op.create_index("ux_rede_conexoes_b", "rede_conexoes", ["porta_b_id", sa.text("coalesce(lado_b, '')")], unique=True,
                    postgresql_where=sa.text("porta_b_id IS NOT NULL"), sqlite_where=sa.text("porta_b_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ux_rede_conexoes_b", table_name="rede_conexoes")
    op.drop_index("ux_rede_conexoes_a", table_name="rede_conexoes")
    # Volta a uma ligação por porta: num patch panel com os dois lados ligados, fica só a da frente
    op.execute("DELETE FROM rede_conexoes WHERE lado_a = 'fundo' AND EXISTS (SELECT 1 FROM rede_conexoes c2 WHERE c2.id <> rede_conexoes.id "
               "AND (c2.porta_a_id = rede_conexoes.porta_a_id OR c2.porta_b_id = rede_conexoes.porta_a_id))")
    op.create_index("ux_rede_conexoes_a", "rede_conexoes", ["porta_a_id"], unique=True)
    op.create_index("ux_rede_conexoes_b", "rede_conexoes", ["porta_b_id"], unique=True,
                    postgresql_where=sa.text("porta_b_id IS NOT NULL"), sqlite_where=sa.text("porta_b_id IS NOT NULL"))
    with op.batch_alter_table("rede_conexoes") as tabela:
        tabela.drop_constraint("ck_rede_conexoes_lado_b", type_="check")
        tabela.drop_constraint("ck_rede_conexoes_lado_a", type_="check")
    op.alter_column("rede_portas", "descricao", server_default="")
    op.drop_column("rede_portas", "observacao")
    op.drop_column("rede_conexoes", "lado_b")
    op.drop_column("rede_conexoes", "lado_a")
