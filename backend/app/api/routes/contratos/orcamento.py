# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de previsão orçamentária e Notas de Empenho.
"""Rotas de previsão orçamentária e Notas de Empenho (`/api/contratos/{contrato_id}/…`)."""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import SEM_VINCULO, pode_ler, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.contratos.orcamento import GravacaoNotaEmpenho, GravacaoPrevisao, LeituraNotaEmpenho, Previsao
from app.services.contratos import servico_orcamento as servico

roteador = APIRouter(prefix="/contratos/{contrato_id}", tags=["Contratos: orçamento"], responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADO = resposta_nao_encontrado("Contrato")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@roteador.get(
    "/previsao",
    response_model=Previsao,
    summary="Previsão orçamentária",
    description="Grade de apontamentos sob demanda por vigência e tabela mensal consolidada (pró-rata 30/360). "
    "Exige ACL `contratos` ≥ LEITURA.",
    responses=NAO_ENCONTRADO,
)
def consultar_previsao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)) -> Previsao:
    with traduzir_erros():
        return servico.montar_previsao(sessao, contrato_id, usuario)


@roteador.put(
    "/previsao/{sequencia_vigencia}",
    response_model=Previsao,
    summary="Salvar previsão da vigência",
    description="Substitui os apontamentos sob demanda da vigência e sela a previsão. Nenhum saldo pode ficar negativo. "
    "Depois de selada, só o SuperRoot altera. Exige poder editar o contrato.",
    responses={**NAO_ENCONTRADO, **INVALIDO, **SEM_VINCULO},
)
def salvar_previsao(
    contrato_id: uuid.UUID,
    sequencia_vigencia: int,
    dados: GravacaoPrevisao,
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(pode_modificar),
) -> Previsao:
    with traduzir_erros(sessao):
        servico.salvar_previsao(sessao, contrato_id, sequencia_vigencia, dados, autor)
        return servico.montar_previsao(sessao, contrato_id, autor)


@roteador.get(
    "/previsao/{sequencia_vigencia}/xlsx",
    summary="Exportar previsão da vigência (XLSX)",
    description="Tabela mensal e itens por competência. Exige ACL `contratos` ≥ LEITURA.",
    responses={status.HTTP_200_OK: {"content": {XLSX: {}}, "description": "Planilha."}, **NAO_ENCONTRADO},
)
def exportar_previsao(contrato_id: uuid.UUID, sequencia_vigencia: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        conteudo, nome = servico.planilha_previsao(sessao, contrato_id, sequencia_vigencia)
    return Response(conteudo, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@roteador.get(
    "/notas-empenho",
    response_model=list[LeituraNotaEmpenho],
    summary="Notas de Empenho do contrato",
    description="Saldo, faixa de consumo e extrato de cada NE. Exige ACL `contratos` ≥ LEITURA.",
    responses=NAO_ENCONTRADO,
)
def listar_notas(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> list[LeituraNotaEmpenho]:
    with traduzir_erros():
        return servico.listar_notas(sessao, contrato_id)


@roteador.post(
    "/notas-empenho",
    response_model=list[LeituraNotaEmpenho],
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar Nota de Empenho",
    description="Número único no contrato (até 30) e valor original > 0. Exige poder editar o contrato. Devolve a lista.",
    responses={**NAO_ENCONTRADO, **CONFLITO, **SEM_VINCULO},
)
def criar_nota(
    contrato_id: uuid.UUID, dados: GravacaoNotaEmpenho, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)
) -> list[LeituraNotaEmpenho]:
    with traduzir_erros(sessao):
        servico.criar_nota(sessao, contrato_id, dados, autor)
        return servico.listar_notas(sessao, contrato_id)


@roteador.put(
    "/notas-empenho/{nota_id}",
    response_model=list[LeituraNotaEmpenho],
    summary="Alterar Nota de Empenho",
    description="O valor não pode ficar abaixo do já consumido. Exige poder editar o contrato. Devolve a lista.",
    responses={**resposta_nao_encontrado("Contrato ou NE"), **INVALIDO, **CONFLITO, **SEM_VINCULO},
)
def alterar_nota(
    contrato_id: uuid.UUID,
    nota_id: uuid.UUID,
    dados: GravacaoNotaEmpenho,
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(pode_modificar),
) -> list[LeituraNotaEmpenho]:
    with traduzir_erros(sessao):
        servico.alterar_nota(sessao, contrato_id, nota_id, dados, autor)
        return servico.listar_notas(sessao, contrato_id)


@roteador.delete(
    "/notas-empenho/{nota_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir Nota de Empenho",
    description="Só NEs sem vínculo com competências e sem débitos. Exige poder editar o contrato.",
    responses={**resposta_nao_encontrado("Contrato ou NE"), **INVALIDO, **SEM_VINCULO},
)
def excluir_nota(contrato_id: uuid.UUID, nota_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)) -> Response:
    with traduzir_erros(sessao):
        servico.excluir_nota(sessao, contrato_id, nota_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
