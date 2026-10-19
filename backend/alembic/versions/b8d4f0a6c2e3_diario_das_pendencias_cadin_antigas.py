# Criado por José Eduardo Santana Martins
# Este arquivo serve para registrar no diário de bordo as pendências de CADIN registradas antes da ocorrência automática, nas datas certas.
"""diário de bordo: pendências de CADIN antigas

Desde a ocorrência automática, toda consulta ao CADIN com pendência entra no diário de bordo com a data e hora do registro. Aqui as
consultas **anteriores** a isso ganham a ocorrência, **como se tivessem sido registradas à época**: `criado_em` é o instante da consulta,
`data_ocorrencia` o dia dele em São Paulo, na competência da etapa (se regular), em nome de quem registrou. Sem duplicar: pula as que já têm
ocorrência com o mesmo instante no contrato.

Revision ID: b8d4f0a6c2e3
Revises: a7c3e9f1b5d2
Create Date: 2026-10-16
"""

from html import escape
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision = "b8d4f0a6c2e3"
down_revision = "a7c3e9f1b5d2"
branch_labels = None
depends_on = None

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
MARCA = "<p><strong>Pendência no CADIN</strong> registrada na etapa de CADIN"


def upgrade() -> None:
    conexao = op.get_bind()
    ocorrencias = sa.Table("contratos_diario_ocorrencias", sa.MetaData(), autoload_with=conexao)
    consultas = conexao.execute(sa.text(
        "SELECT q.id, q.pendencia, q.criado_em, q.criado_por_id, q.criado_por_nome, c.contrato_id, c.competencia, c.tipo "
        "FROM contratos_competencias_cadin q JOIN contratos_competencias c ON c.id = q.competencia_id "
        "WHERE q.possui_pendencia ORDER BY q.criado_em"
    )).all()
    for consulta in consultas:
        ja_existe = conexao.execute(
            sa.select(ocorrencias.c.id).where(ocorrencias.c.contrato_id == consulta.contrato_id, ocorrencias.c.criado_em == consulta.criado_em,
                                              ocorrencias.c.descricao.like(MARCA + "%"))
        ).first()
        if ja_existe:
            continue
        momento = consulta.criado_em.astimezone(SAO_PAULO)
        relato = (f"{MARCA} da competência {consulta.competencia:%m/%Y} em {momento:%d/%m/%Y} às {momento:%H:%M}.</p>"
                  f"<p><strong>Pendência:</strong> {escape(consulta.pendencia or '')}</p>")
        conexao.execute(ocorrencias.insert().values(
            id=__import__("uuid").uuid4(), contrato_id=consulta.contrato_id, data_ocorrencia=momento.date(),
            competencia_afetada=consulta.competencia if consulta.tipo == "regular" else None, descricao=relato,
            possui_glosa=False, impacta_avaliacao=False, registrada_por_id=consulta.criado_por_id,
            registrada_por_nome=consulta.criado_por_nome, registrada_por_papel="", criado_em=consulta.criado_em, email_destinatarios=[],
        ))


def downgrade() -> None:
    # Remove só as ocorrências automáticas do CADIN (a marca está no começo do relato)
    op.get_bind().execute(sa.text("DELETE FROM contratos_diario_ocorrencias WHERE descricao LIKE :m"), {"m": MARCA + "%"})
