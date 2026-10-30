# Criado por José Eduardo Santana Martins
# Este arquivo serve para liberar o modelo "prorrogacao", guardar os dados digitados das minutas e semear os sete modelos padrão.
"""minutas da prorrogação contratual

- `contratos_modelos`: o tipo `prorrogacao` entra na check constraint (minutas e despachos da prorrogação, uma máscara ativa por variante);
- `contratos_prorrogacoes_processos`: `dados_minuta` (JSON) com o que a equipe digita para completar as minutas;
- semeia os sete modelos padrão (a partir de `apoio/Prorrogações`), só os das variantes que ainda não tiverem modelo.

Revision ID: a4c8e2f6b0d3
Revises: e2a6c0d4f8b1
Create Date: 2026-10-27
"""

import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = "a4c8e2f6b0d3"
down_revision = "e2a6c0d4f8b1"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    from app.services.contratos.modelos_prorrogacao_padrao import MODELOS

    with op.batch_alter_table("contratos_modelos") as lote:
        lote.drop_constraint("ck_contratos_modelos_tipo", type_="check")
        lote.create_check_constraint("ck_contratos_modelos_tipo", "tipo IN ('checklist', 'formulario', 'portaria', 'despacho', 'email_cadin', 'email_ob', 'prorrogacao')")
    op.add_column("contratos_prorrogacoes_processos", sa.Column("dados_minuta", JSON, nullable=False, server_default=sa.text("'{}'")))
    conexao = op.get_bind()
    existentes = {
        (json.loads(c) if isinstance(c, str) else c).get("variante")
        for (c,) in conexao.execute(sa.text("SELECT conteudo FROM contratos_modelos WHERE tipo = 'prorrogacao'"))
    }
    for variante, (nome, html) in MODELOS.items():
        if variante in existentes:
            continue
        conexao.execute(sa.text(
            "INSERT INTO contratos_modelos (id, tipo, nome, conteudo, ativo, criado_em, atualizado_em) "
            "VALUES (:id, 'prorrogacao', :nome, CAST(:conteudo AS JSON), true, now(), now())"
        ), {"id": uuid.uuid4(), "nome": nome, "conteudo": json.dumps({"html": html, "variante": variante}, ensure_ascii=False)})


def downgrade() -> None:
    op.execute("DELETE FROM contratos_modelos WHERE tipo = 'prorrogacao'")
    op.drop_column("contratos_prorrogacoes_processos", "dados_minuta")
    with op.batch_alter_table("contratos_modelos") as lote:
        lote.drop_constraint("ck_contratos_modelos_tipo", type_="check")
        lote.create_check_constraint("ck_contratos_modelos_tipo", "tipo IN ('checklist', 'formulario', 'portaria', 'despacho', 'email_cadin', 'email_ob')")
