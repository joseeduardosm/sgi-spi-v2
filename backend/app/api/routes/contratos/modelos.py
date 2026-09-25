# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas dos modelos globais de checklist e de formulário.
"""Modelos globais de checklist e de formulário (`/api/contratos/modelos`)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import pode_ler, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Papel, Usuario
from app.schemas.contratos.execucao import GravacaoModelo, LeituraModelo
from app.services.contratos import servico_configuracao_execucao as servico

roteador = APIRouter(prefix="/contratos/modelos", tags=["Contratos: modelos globais"], responses=RESPOSTAS_AUTENTICADAS)
super_root = exigir_papeis(Papel.SUPER_ROOT)
NAO_ENCONTRADO = resposta_nao_encontrado("Modelo")


@roteador.get("", response_model=list[LeituraModelo], summary="Listar modelos globais",
              description="Modelos de checklist e de formulário para clonar nos contratos. Exige ACL `contratos` ≥ LEITURA.")
def listar_modelos(
    tipo: Literal["checklist", "formulario"] | None = Query(None),
    somente_ativos: bool = Query(True),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(pode_ler),
):
    return servico.listar_modelos(sessao, tipo, somente_ativos)


@roteador.post("", response_model=LeituraModelo, status_code=status.HTTP_201_CREATED, summary="Criar modelo global",
               description="Restrito ao SuperRoot.", responses=INVALIDO)
def criar_modelo(dados: GravacaoModelo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)):
    with traduzir_erros(sessao):
        return servico.leitura_modelo(servico.salvar_modelo(sessao, dados, autor))


@roteador.put("/{modelo_id}", response_model=LeituraModelo, summary="Alterar modelo global",
              description="O tipo não muda. Restrito ao SuperRoot.", responses={**NAO_ENCONTRADO, **INVALIDO})
def alterar_modelo(modelo_id: uuid.UUID, dados: GravacaoModelo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)):
    with traduzir_erros(sessao):
        return servico.leitura_modelo(servico.salvar_modelo(sessao, dados, autor, modelo_id))


@roteador.delete("/{modelo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir modelo global",
                 description="As cópias já feitas nos contratos não mudam. Restrito ao SuperRoot.", responses=NAO_ENCONTRADO)
def excluir_modelo(modelo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> Response:
    with traduzir_erros(sessao):
        servico.excluir_modelo(sessao, modelo_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
