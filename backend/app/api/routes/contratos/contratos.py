"""Rotas do contrato (`/api/contratos`): carteira, cadastro, detalhe, documentos e histórico."""

import uuid

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import (
    ARQUIVO_RECUSADO,
    SEM_VINCULO,
    arquivo_pdf,
    controle_total,
    pode_ler,
    pode_modificar,
    traduzir_erros,
)
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.contratos.contratos import (
    AlteracaoCampo,
    DetalheContrato,
    GravacaoContrato,
    LeituraDocumento,
    PaginaContratos,
    ProximoNumero,
)
from app.schemas.usuarios import OpcaoUsuario
from app.services import servico_admin_usuarios
from app.services.contratos import servico_contratos as servico

roteador = APIRouter(prefix="/contratos", tags=["Contratos"], responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADO = resposta_nao_encontrado("Contrato")
PDF = {status.HTTP_200_OK: {"content": {"application/pdf": {}}, "description": "Arquivo PDF."}}


@roteador.get(
    "",
    response_model=PaginaContratos,
    summary="Carteira de contratos",
    description="Busca por número (`012/2026`), empresa, apelido ou objeto. Mais recentes primeiro. "
    "Exige ACL `contratos` ≥ LEITURA.",
)
def listar_contratos(
    busca: str | None = Query(None, max_length=100),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(25, ge=1, le=100),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(pode_ler),
) -> PaginaContratos:
    return servico.listar_contratos(sessao, busca, pagina, tamanho_pagina)


@roteador.get(
    "/proximo-numero",
    response_model=ProximoNumero,
    summary="Próximo número de contrato do ano",
    description="Sugestão para o cadastro: maior sequencial do ano + 1. Exige ACL `contratos` ≥ LEITURA.",
)
def proximo_numero(
    ano: int = Query(..., ge=2000, le=9999), sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)
) -> ProximoNumero:
    return servico.proximo_numero(sessao, ano)


@roteador.get(
    "/opcoes-usuarios",
    response_model=list[OpcaoUsuario],
    summary="Usuários para a equipe de gestão e fiscalização",
    description="Usuários ativos do portal, para os seis papéis da equipe. Não exige ACL `usuarios`. "
    "Exige ACL `contratos` ≥ MODIFICACAO.",
)
def opcoes_usuarios(
    busca: str | None = Query(None, max_length=100),
    limite: int = Query(20, ge=1, le=100),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(pode_modificar),
) -> list[OpcaoUsuario]:
    return servico_admin_usuarios.opcoes(sessao, busca, limite)


@roteador.get("/{contrato_id}", response_model=DetalheContrato, summary="Detalhe do contrato", responses=NAO_ENCONTRADO,
              description="Dados, vigências, itens com saldos, equipe vigente e permissões do usuário. Exige ACL `contratos` ≥ LEITURA.")
def consultar_contrato(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)) -> DetalheContrato:
    with traduzir_erros():
        return servico.detalhar_contrato(sessao, contrato_id, usuario)


@roteador.post(
    "",
    response_model=DetalheContrato,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar contrato",
    description="Cria o contrato com itens e equipe. O usuário vira o criador. Exige ACL `contratos` ≥ MODIFICACAO.",
    responses={**INVALIDO, **CONFLITO},
)
def criar_contrato(dados: GravacaoContrato, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)) -> DetalheContrato:
    with traduzir_erros(sessao):
        contrato = servico.criar_contrato(sessao, dados, autor)
    return servico.detalhar_contrato(sessao, contrato.id, autor)


@roteador.put(
    "/{contrato_id}",
    response_model=DetalheContrato,
    summary="Alterar contrato",
    description="Substitui dados, equipe e a lista de itens. Exige `versao` igual à atual (senão 409). "
    "Itens salvos não mudam nome, tipo nem faturamento. Somente criador, equipe vigente ou SuperRoot, com ACL ≥ MODIFICACAO.",
    responses={**NAO_ENCONTRADO, **INVALIDO, **CONFLITO, **SEM_VINCULO},
)
def alterar_contrato(
    contrato_id: uuid.UUID, dados: GravacaoContrato, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)
) -> DetalheContrato:
    with traduzir_erros(sessao):
        servico.alterar_contrato(sessao, contrato_id, dados, autor)
    return servico.detalhar_contrato(sessao, contrato_id, autor)


@roteador.delete(
    "/{contrato_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir contrato",
    description="Remove o contrato e tudo o que depende dele. Exige ACL `contratos` = CONTROLE_TOTAL.",
    responses=NAO_ENCONTRADO,
)
def excluir_contrato(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(controle_total)) -> Response:
    with traduzir_erros(sessao):
        servico.excluir_contrato(sessao, contrato_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get(
    "/{contrato_id}/historico",
    response_model=list[AlteracaoCampo],
    summary="Histórico de alterações por campo",
    description="Quem alterou, quando, de → para. Mais recentes primeiro. Exige ACL `contratos` ≥ LEITURA.",
    responses=NAO_ENCONTRADO,
)
def historico(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> list[AlteracaoCampo]:
    with traduzir_erros():
        return servico.historico(sessao, contrato_id)


@roteador.get(
    "/{contrato_id}/documentos",
    response_model=list[LeituraDocumento],
    summary="Documentos importantes",
    description="Catálogo 001–023 (e termos aditivos 024+), anexados ou não. Exige ACL `contratos` ≥ LEITURA.",
    responses=NAO_ENCONTRADO,
)
def listar_documentos(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> list[LeituraDocumento]:
    with traduzir_erros():
        return servico.listar_documentos(sessao, contrato_id)


@roteador.post(
    "/{contrato_id}/documentos/{codigo}",
    response_model=list[LeituraDocumento],
    summary="Anexar documento importante",
    description="`multipart/form-data` com o PDF em `arquivo`. Substitui o anterior. Códigos 1 a 23. "
    "Somente criador, equipe vigente ou SuperRoot, com ACL ≥ MODIFICACAO. Devolve a lista atualizada.",
    responses={**NAO_ENCONTRADO, **ARQUIVO_RECUSADO, **SEM_VINCULO},
)
def enviar_documento(
    contrato_id: uuid.UUID,
    codigo: int,
    arquivo: UploadFile = File(..., description="PDF"),
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(pode_modificar),
) -> list[LeituraDocumento]:
    with traduzir_erros(sessao):
        servico.enviar_documento(sessao, contrato_id, codigo, *arquivo_pdf(arquivo), autor)
        return servico.listar_documentos(sessao, contrato_id)


@roteador.get(
    "/{contrato_id}/documentos/{codigo}/arquivo",
    response_class=FileResponse,
    summary="Baixar documento importante",
    description="Nome padronizado `PREFIXO_SPI_NNN_AAAA.pdf`. Exige ACL `contratos` ≥ LEITURA.",
    responses={**PDF, **resposta_nao_encontrado("Documento")},
)
def baixar_documento(contrato_id: uuid.UUID, codigo: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        return servico.documento_para_download(sessao, contrato_id, codigo)
