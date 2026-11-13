"""
===============================================================================
ARQUIVO: f2b8d4c0a6e1_email_de_pagamento_da_ob.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que libera o modelo email_ob (e-mail de pagamento por máscara)
e guarda o resultado do e-mail enviado ao lançar a OB.

RESUMO TÉCNICO:
- contratos_modelos: o tipo email_ob entra na check constraint (máscara do
  e-mail enviado aos prepostos quando a Ordem Bancária é lançada);
- contratos_competencias: colunas do resultado do envio (email_ob_enviado_em,
  email_ob_ok, email_ob_destinatarios, email_ob_erro);
- semeia a máscara padrão ativa, só se ainda não houver uma.

FINALIDADE DE NEGÓCIO:
OB (Ordem Bancária) é o pagamento efetivo à empresa. Ao registrá-la, o SGI
avisa os prepostos (representantes da empresa no contrato) que a competência
(mês de execução) foi paga, e guarda se o e-mail saiu ou falhou.

CONTEXTO NO SISTEMA:
Tabelas contratos_modelos e contratos_competencias; modelos editados na tela de
Modelos dos contratos e envio feito pelo serviço de execução/notificações.
Aplicada com 'alembic upgrade head' (o instalador e a atualização do sistema
rodam esse comando).

Revision ID: f2b8d4c0a6e1
Revises: e1a7c3b9d5f2
Create Date: 2026-10-18

===============================================================================
"""

import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = "f2b8d4c0a6e1"
down_revision = "e1a7c3b9d5f2"
branch_labels = None
depends_on = None

# Máscara padrão do e-mail. Os marcadores com "#" (#nrocontrato, #valorpago...) são
# trocados pelos dados reais da competência na hora do envio, pelo serviço de e-mail.
ASSUNTO = "Contrato #nrocontrato - #mescompetencia - Pagamento efetuado"
HTML = (
    "<p>Prezados,</p>"
    "<p>Informamos que a competência <b>#mescompetencia</b> do contrato <b>#nrocontrato</b> (#razaosocialempresa, CNPJ #cnpjempresa), "
    "no valor de <b>#valorpago</b>, foi paga em <b>#datapagamento</b>.</p>"
    "<p>A Ordem Bancária foi registrada no SGI SPI por #usuarioob.</p>"
    "<p>Atenciosamente,<br/>Secretaria de Parcerias em Investimentos</p>"
)


def upgrade() -> None:
    """Libera o tipo email_ob, cria as colunas de resultado do envio e semeia a máscara."""
    # OB = Ordem Bancária, o documento do pagamento efetivo à empresa contratada.
    # A check constraint lista os tipos de modelo aceitos: recria incluindo email_ob.
    with op.batch_alter_table("contratos_modelos") as lote:
        lote.drop_constraint("ck_contratos_modelos_tipo", type_="check")
        lote.create_check_constraint("ck_contratos_modelos_tipo", "tipo IN ('checklist', 'formulario', 'portaria', 'despacho', 'email_cadin', 'email_ob')")
    op.add_column("contratos_competencias", sa.Column("email_ob_enviado_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contratos_competencias", sa.Column("email_ob_ok", sa.Boolean(), nullable=True))
    op.add_column("contratos_competencias", sa.Column("email_ob_destinatarios", sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
                                                      nullable=False, server_default=sa.text("'[]'")))
    op.add_column("contratos_competencias", sa.Column("email_ob_erro", sa.Text(), nullable=True))
    # Só cria a máscara padrão se ainda não existir nenhuma do tipo email_ob
    conexao = op.get_bind()
    if not conexao.scalar(sa.text("SELECT count(*) FROM contratos_modelos WHERE tipo = 'email_ob'")):
        conexao.execute(sa.text(
            "INSERT INTO contratos_modelos (id, tipo, nome, conteudo, ativo, criado_em, atualizado_em) "
            "VALUES (:id, 'email_ob', 'E-mail de pagamento (OB)', CAST(:conteudo AS JSON), true, now(), now())"
        ), {"id": uuid.uuid4(), "conteudo": json.dumps({"assunto": ASSUNTO, "html": HTML}, ensure_ascii=False)})


def downgrade() -> None:
    """Remove as máscaras email_ob, as colunas do envio e volta a check constraint antiga."""
    op.execute("DELETE FROM contratos_modelos WHERE tipo = 'email_ob'")
    for coluna in ("email_ob_erro", "email_ob_destinatarios", "email_ob_ok", "email_ob_enviado_em"):
        op.drop_column("contratos_competencias", coluna)
    with op.batch_alter_table("contratos_modelos") as lote:
        lote.drop_constraint("ck_contratos_modelos_tipo", type_="check")
        lote.create_check_constraint("ck_contratos_modelos_tipo", "tipo IN ('checklist', 'formulario', 'portaria', 'despacho', 'email_cadin')")
