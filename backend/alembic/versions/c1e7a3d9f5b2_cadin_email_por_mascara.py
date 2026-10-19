# Criado por José Eduardo Santana Martins
# Este arquivo serve para liberar o modelo "email_cadin" e guardar o resultado do envio do e-mail da pendência no CADIN.
"""contratos: e-mail de CADIN por máscara

- `contratos_modelos`: o tipo `email_cadin` entra na check constraint (máscara do e-mail enviado aos prepostos quando a consulta ao CADIN acusa pendência);
  um modelo padrão **ativo** é semeado (editável em Contratos › Modelos) para a etapa não ficar sem máscara.
- `contratos_competencias_cadin`: resultado do envio (`email_enviado_em`, `email_ok`, `email_destinatarios`, `email_erro`).

Revision ID: c1e7a3d9f5b2
Revises: b9d5f7a2c4e6
Create Date: 2026-10-16 10:00:00
"""
import json
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c1e7a3d9f5b2'
down_revision: Union[str, Sequence[str], None] = 'b9d5f7a2c4e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ASSUNTO = "Contrato #nrocontrato - #mescompetencia - Pendência no CADIN"
HTML = (
    "<p>Prezados,</p>"
    "<p>Na consulta ao CADIN realizada em <b>#dataconsulta</b>, às <b>#horaconsulta</b>, foi encontrada pendência em nome de "
    "<b>#razaosocialempresa</b> (CNPJ #cnpjempresa), relacionada ao contrato <b>#nrocontrato</b>, competência <b>#mescompetencia</b>.</p>"
    "<p><b>Pendência:</b> #pendencia</p>"
    "<p>Solicitamos a regularização e o envio de comprovante para que o processo de pagamento possa prosseguir.</p>"
    "<p>Atenciosamente,<br/>#usuarioconsulta</p>"
)


def upgrade() -> None:
    with op.batch_alter_table('contratos_modelos') as lote:
        lote.drop_constraint('ck_contratos_modelos_tipo', type_='check')
        lote.create_check_constraint('ck_contratos_modelos_tipo', "tipo IN ('checklist', 'formulario', 'portaria', 'despacho', 'email_cadin')")
    op.add_column('contratos_competencias_cadin', sa.Column('email_enviado_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column('contratos_competencias_cadin', sa.Column('email_ok', sa.Boolean(), nullable=True))
    op.add_column('contratos_competencias_cadin', sa.Column('email_destinatarios', sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), 'postgresql'), nullable=True))
    op.add_column('contratos_competencias_cadin', sa.Column('email_erro', sa.Text(), nullable=True))
    # Modelo padrão ativo (só se ainda não houver um)
    conexao = op.get_bind()
    if not conexao.scalar(sa.text("SELECT count(*) FROM contratos_modelos WHERE tipo = 'email_cadin'")):
        conexao.execute(sa.text(
            "INSERT INTO contratos_modelos (id, tipo, nome, conteudo, ativo, criado_em, atualizado_em) "
            "VALUES (:id, 'email_cadin', 'E-mail de pendência no CADIN', CAST(:conteudo AS JSON), true, now(), now())"
        ), {"id": uuid.uuid4(), "conteudo": json.dumps({"assunto": ASSUNTO, "html": HTML}, ensure_ascii=False)})


def downgrade() -> None:
    op.execute("DELETE FROM contratos_modelos WHERE tipo = 'email_cadin'")
    for coluna in ('email_erro', 'email_destinatarios', 'email_ok', 'email_enviado_em'):
        op.drop_column('contratos_competencias_cadin', coluna)
    with op.batch_alter_table('contratos_modelos') as lote:
        lote.drop_constraint('ck_contratos_modelos_tipo', type_='check')
        lote.create_check_constraint('ck_contratos_modelos_tipo', "tipo IN ('checklist', 'formulario', 'portaria', 'despacho')")
