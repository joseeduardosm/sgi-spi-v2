# Criado por José Eduardo Santana Martins
# Este arquivo serve para liberar o modelo "email_ob" e guardar o resultado do e-mail de pagamento enviado ao lançar a OB.
"""e-mail de pagamento (OB) por máscara

- `contratos_modelos`: o tipo `email_ob` entra na check constraint (máscara do e-mail enviado aos prepostos quando a Ordem Bancária é lançada);
- `contratos_competencias`: resultado do envio (`email_ob_enviado_em`, `email_ob_ok`, `email_ob_destinatarios`, `email_ob_erro`);
- semeia a máscara padrão ativa (só se ainda não houver uma).

Revision ID: f2b8d4c0a6e1
Revises: e1a7c3b9d5f2
Create Date: 2026-10-18
"""

import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = "f2b8d4c0a6e1"
down_revision = "e1a7c3b9d5f2"
branch_labels = None
depends_on = None

ASSUNTO = "Contrato #nrocontrato - #mescompetencia - Pagamento efetuado"
HTML = (
    "<p>Prezados,</p>"
    "<p>Informamos que a competência <b>#mescompetencia</b> do contrato <b>#nrocontrato</b> (#razaosocialempresa, CNPJ #cnpjempresa), "
    "no valor de <b>#valorpago</b>, foi paga em <b>#datapagamento</b>.</p>"
    "<p>A Ordem Bancária foi registrada no SGI SPI por #usuarioob.</p>"
    "<p>Atenciosamente,<br/>Secretaria de Parcerias em Investimentos</p>"
)


def upgrade() -> None:
    with op.batch_alter_table("contratos_modelos") as lote:
        lote.drop_constraint("ck_contratos_modelos_tipo", type_="check")
        lote.create_check_constraint("ck_contratos_modelos_tipo", "tipo IN ('checklist', 'formulario', 'portaria', 'despacho', 'email_cadin', 'email_ob')")
    op.add_column("contratos_competencias", sa.Column("email_ob_enviado_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contratos_competencias", sa.Column("email_ob_ok", sa.Boolean(), nullable=True))
    op.add_column("contratos_competencias", sa.Column("email_ob_destinatarios", sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
                                                      nullable=False, server_default=sa.text("'[]'")))
    op.add_column("contratos_competencias", sa.Column("email_ob_erro", sa.Text(), nullable=True))
    conexao = op.get_bind()
    if not conexao.scalar(sa.text("SELECT count(*) FROM contratos_modelos WHERE tipo = 'email_ob'")):
        conexao.execute(sa.text(
            "INSERT INTO contratos_modelos (id, tipo, nome, conteudo, ativo, criado_em, atualizado_em) "
            "VALUES (:id, 'email_ob', 'E-mail de pagamento (OB)', CAST(:conteudo AS JSON), true, now(), now())"
        ), {"id": uuid.uuid4(), "conteudo": json.dumps({"assunto": ASSUNTO, "html": HTML}, ensure_ascii=False)})


def downgrade() -> None:
    op.execute("DELETE FROM contratos_modelos WHERE tipo = 'email_ob'")
    for coluna in ("email_ob_erro", "email_ob_destinatarios", "email_ob_ok", "email_ob_enviado_em"):
        op.drop_column("contratos_competencias", coluna)
    with op.batch_alter_table("contratos_modelos") as lote:
        lote.drop_constraint("ck_contratos_modelos_tipo", type_="check")
        lote.create_check_constraint("ck_contratos_modelos_tipo", "tipo IN ('checklist', 'formulario', 'portaria', 'despacho', 'email_cadin')")
