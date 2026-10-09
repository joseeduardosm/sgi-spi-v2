# Criado por José Eduardo Santana Martins
# Este arquivo serve para aceitar o tipo "portaria" nos modelos globais e cadastrar as duas máscaras iniciais (com e sem portaria anterior).
"""máscaras de portaria nos modelos globais

Revision ID: e7a2b4d6f8c1
Revises: d6f1a3c5e7b9
Create Date: 2026-10-09 15:00:00
"""

import uuid
from datetime import UTC, datetime
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "e7a2b4d6f8c1"
down_revision: str | Sequence[str] | None = "d6f1a3c5e7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DECRETO = "Decreto estadual nº 68.220, de 15 de dezembro de 2023"


def _p(texto: str, alinhamento: str = "justify") -> str:
    return f'<p style="text-align: {alinhamento}">{texto}</p>'


def _artigo(rotulo: str, texto: str) -> str:
    return _p(f"<strong>{rotulo}</strong> {texto}")


def _mascara(com_anterior: bool) -> str:
    partes = [
        _p("<strong>Portaria SPI SSGC nº #numeroportaria, de #anoportaria</strong>", "center"),
        _p("Designa gestor e fiscal para o acompanhamento e a fiscalização da execução do Contrato SPI nº #numerodocontrato."),
        _p("O SUBSECRETÁRIO DE GESTÃO CORPORATIVA DA SECRETARIA DE PARCERIAS EM INVESTIMENTOS, no uso da atribuição prevista no artigo 12, inciso IV, "
           "da Resolução SPI nº 17, de 31 de março de 2025, e nos termos do artigo 117 da Lei federal nº 14.133, de 1º de abril de 2021, e dos artigos 3º e 15 "
           f"do {DECRETO}, resolve:"),
        _artigo("Artigo 1º -", f"Nos termos do artigo 15 do {DECRETO}, designar os servidores adiante identificados para atuarem como gestores e fiscais do "
                "Contrato SPI nº #numerodocontrato, firmado com a Empresa #contratada, inscrita no CNPJ sob o nº #cnpjcontratada, cujo objeto é "
                "#objetodocontrato, conforme os autos do Processo SEI nº #nroprocessosei."),
        _p("I – #nomegestor – RS: #rsgestor – <strong>Gestor</strong>"),
        _p("II – #nomegestorsuplente – RS: #rsgestorsuplente – <strong>Gestor suplente</strong>"),
        _p("III – #nomefiscal – RS: #rsfiscal – <strong>Fiscal</strong>"),
        _artigo("Artigo 2º -", "Aos gestores do contrato compete acompanhar, com o auxílio da fiscalização, todas as etapas da execução contratual e exercer as "
                f"atribuições previstas no artigo 16 do {DECRETO}."),
        _artigo("Artigo 3º -", f"Aos fiscais do contrato compete exercer as atribuições de fiscalização técnica e administrativa previstas nos artigos 17 a 19 do "
                f"{DECRETO}, observadas as características do objeto contratado."),
    ]
    if com_anterior:
        partes += [_artigo("Artigo 4º -", "Fica revogada a Portaria #nomedocumento nº #numeroportariaanterior, de #diaportariaanterior de #mesportariaanterior de "
                           "#anoportariaanterior, que dispõe sobre a mesma matéria."),
                   _artigo("Artigo 5º -", "Esta Portaria entra em vigor na data de sua publicação.")]
    else:
        partes += [_artigo("Artigo 4º -", "Esta Portaria entra em vigor na data de sua publicação.")]
    partes += [_p("<strong>#nomeautoridade</strong>", "center"), _p("Subsecretário de Gestão Corporativa", "center"),
               _p("Secretaria de Parcerias em Investimentos", "center")]
    return "".join(partes)


def upgrade() -> None:
    """Aceita o tipo `portaria` e cadastra as duas máscaras iniciais, ativas (editáveis em Contratos → Modelos)."""
    op.drop_constraint("ck_contratos_modelos_tipo", "contratos_modelos", type_="check")
    op.create_check_constraint("ck_contratos_modelos_tipo", "contratos_modelos", "tipo IN ('checklist', 'formulario', 'portaria')")
    modelos = sa.table("contratos_modelos", sa.column("id", sa.Uuid()), sa.column("tipo", sa.String()), sa.column("nome", sa.String()),
                       sa.column("conteudo", sa.dialects.postgresql.JSONB()), sa.column("ativo", sa.Boolean()),
                       sa.column("criado_em", sa.DateTime(timezone=True)), sa.column("atualizado_em", sa.DateTime(timezone=True)))
    agora = datetime.now(UTC)
    op.bulk_insert(modelos, [
        {"id": uuid.uuid4(), "tipo": "portaria", "nome": "Portaria de designação (com portaria anterior)", "ativo": True, "criado_em": agora, "atualizado_em": agora,
         "conteudo": {"html": _mascara(True), "variante": "com_anterior"}},
        {"id": uuid.uuid4(), "tipo": "portaria", "nome": "Portaria de designação (sem portaria anterior)", "ativo": True, "criado_em": agora, "atualizado_em": agora,
         "conteudo": {"html": _mascara(False), "variante": "sem_anterior"}},
    ])


def downgrade() -> None:
    """Remove as máscaras e volta a restrição aos dois tipos antigos."""
    op.execute("DELETE FROM contratos_modelos WHERE tipo = 'portaria'")
    op.drop_constraint("ck_contratos_modelos_tipo", "contratos_modelos", type_="check")
    op.create_check_constraint("ck_contratos_modelos_tipo", "contratos_modelos", "tipo IN ('checklist', 'formulario')")
