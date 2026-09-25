# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de empresas contratadas e prepostos.
"""Rotas de empresas contratadas e prepostos (`/api/contratos/empresas`).

A empresa é a pessoa jurídica contratada (CNPJ). Os prepostos são os representantes indicados
por ela para tratar do contrato; são apenas contatos, não usuários do portal.
Consultar exige leitura em `contratos`; cadastrar e alterar, modificação; excluir empresa, controle total.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import controle_total, pode_ler, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.contratos.empresas import (
    DetalheEmpresa,
    GravacaoEmpresa,
    GravacaoPreposto,
    OpcaoEmpresa,
    PaginaEmpresas,
)
from app.services.contratos import servico_empresas as servico

roteador = APIRouter(prefix="/contratos/empresas", tags=["Contratos: empresas"], responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADA = resposta_nao_encontrado("Empresa")


@roteador.get(
    "",
    response_model=PaginaEmpresas,
    summary="Listar empresas contratadas",
    description="Pesquisa em qualquer dado da empresa, dos prepostos e dos contratos. Paginação e ordenação no servidor. "
    "Exige ACL `contratos` ≥ LEITURA.",
)
def listar_empresas(
    busca: str | None = Query(None, max_length=100),
    ordenar: Literal["cnpj", "razao_social", "nome_fantasia", "endereco"] = Query("razao_social"),
    direcao: Literal["asc", "desc"] = Query("asc"),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(25, ge=1, le=100),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(pode_ler),
) -> PaginaEmpresas:
    """Lista paginada; a busca e a ordenação são feitas no banco, não no navegador."""
    return servico.listar_empresas(sessao, busca, ordenar, direcao, pagina, tamanho_pagina)


@roteador.get(
    "/opcoes",
    response_model=list[OpcaoEmpresa],
    summary="Opções de empresas para o cadastro de contrato",
    description="Somente empresas ativas, salvo `incluir_inativas=true`. Exige ACL `contratos` ≥ LEITURA.",
)
def opcoes_empresas(
    incluir_inativas: bool = Query(False), sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)
) -> list[OpcaoEmpresa]:
    """Lista curta (id e nome) para o campo de empresa no cadastro de contrato."""
    return servico.opcoes_empresas(sessao, incluir_inativas)


@roteador.get("/{empresa_id}", response_model=DetalheEmpresa, summary="Consultar empresa com prepostos e contratos", responses=NAO_ENCONTRADA)
def consultar_empresa(empresa_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> DetalheEmpresa:
    """Detalhe da empresa com os prepostos e os contratos em que aparece."""
    with traduzir_erros():
        return servico.detalhar_empresa(sessao, empresa_id)


@roteador.post(
    "",
    response_model=DetalheEmpresa,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar empresa",
    description="CNPJ único, validado pelos dígitos verificadores. Exige ACL `contratos` ≥ MODIFICACAO.",
    responses={**CONFLITO},
)
def criar_empresa(dados: GravacaoEmpresa, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)) -> DetalheEmpresa:
    """Cadastra a empresa e devolve o detalhe completo, como a tela espera."""
    # O bloco `with` só envolve a gravação; a leitura final roda depois do commit implícito
    with traduzir_erros(sessao):
        empresa = servico.criar_empresa(sessao, dados, autor)
    return servico.detalhar_empresa(sessao, empresa.id)


@roteador.put(
    "/{empresa_id}",
    response_model=DetalheEmpresa,
    summary="Alterar empresa",
    description="Exige ACL `contratos` ≥ MODIFICACAO.",
    responses={**NAO_ENCONTRADA, **CONFLITO},
)
def alterar_empresa(
    empresa_id: uuid.UUID, dados: GravacaoEmpresa, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)
) -> DetalheEmpresa:
    """Altera os dados da empresa e devolve o detalhe atualizado."""
    with traduzir_erros(sessao):
        servico.alterar_empresa(sessao, empresa_id, dados, autor)
    return servico.detalhar_empresa(sessao, empresa_id)


@roteador.delete(
    "/{empresa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir empresa",
    description="Somente empresas sem contratos (as demais podem ser inativadas). Exige ACL `contratos` = CONTROLE_TOTAL.",
    responses={**NAO_ENCONTRADA, **CONFLITO},
)
def excluir_empresa(empresa_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(controle_total)) -> Response:
    """Exclui a empresa; o serviço recusa (409) se ela tiver contratos."""
    with traduzir_erros(sessao):
        servico.excluir_empresa(sessao, empresa_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post(
    "/{empresa_id}/prepostos",
    response_model=DetalheEmpresa,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar preposto",
    description="O preposto é um contato da empresa, não um usuário do portal. CPF único na empresa. "
    "Exige ACL `contratos` ≥ MODIFICACAO. Devolve a empresa atualizada.",
    responses={**NAO_ENCONTRADA, **CONFLITO},
)
def criar_preposto(
    empresa_id: uuid.UUID, dados: GravacaoPreposto, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)
) -> DetalheEmpresa:
    """Cadastra um preposto e devolve a empresa inteira, para a tela redesenhar a lista."""
    with traduzir_erros(sessao):
        servico.salvar_preposto(sessao, empresa_id, dados, autor)
    return servico.detalhar_empresa(sessao, empresa_id)


@roteador.put(
    "/{empresa_id}/prepostos/{preposto_id}",
    response_model=DetalheEmpresa,
    summary="Alterar preposto",
    description="Exige ACL `contratos` ≥ MODIFICACAO. Devolve a empresa atualizada.",
    responses={**resposta_nao_encontrado("Empresa ou preposto"), **CONFLITO},
)
def alterar_preposto(
    empresa_id: uuid.UUID,
    preposto_id: uuid.UUID,
    dados: GravacaoPreposto,
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(pode_modificar),
) -> DetalheEmpresa:
    """Altera um preposto (o mesmo serviço grava novo ou existente, conforme o `preposto_id`)."""
    with traduzir_erros(sessao):
        servico.salvar_preposto(sessao, empresa_id, dados, autor, preposto_id)
    return servico.detalhar_empresa(sessao, empresa_id)


@roteador.delete(
    "/{empresa_id}/prepostos/{preposto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir preposto",
    description="Exige ACL `contratos` ≥ MODIFICACAO.",
    responses={**resposta_nao_encontrado("Empresa ou preposto"), **INVALIDO},
)
def excluir_preposto(
    empresa_id: uuid.UUID, preposto_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)
) -> Response:
    """Exclui um preposto."""
    with traduzir_erros(sessao):
        servico.excluir_preposto(sessao, empresa_id, preposto_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
