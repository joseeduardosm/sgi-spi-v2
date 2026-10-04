# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de importação de checklists e formulários de avaliação por planilha XLSX.
"""Importação de checklists e formulários de avaliação por XLSX.

Duas famílias de rotas, com o mesmo fluxo (baixar o modelo → prévia → confirmar com o mesmo arquivo):
- no contrato: `/api/contratos/{contrato_id}/{checklists|formularios}/importacao-xlsx` cria uma versão
  **inativa** (é preciso ativá-la depois, como no cadastro manual);
- modelos globais: `/api/contratos/modelos/importacao-xlsx/{checklist|formulario}` cria um modelo global (SuperRoot).

Acesso: ACL `importacao-modelos` ≥ MODIFICACAO **e** ACL `contratos` ≥ MODIFICACAO; no contrato, também o
vínculo exigido para editá-lo (403 `acesso_negado`); nos modelos globais, o papel SuperRoot.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl, exigir_papeis
from app.api.respostas import RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import SEM_VINCULO, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.usuario import Papel, Usuario
from app.schemas.comum import RespostaErro
from app.schemas.contratos.execucao import LeituraChecklist, LeituraFormulario, LeituraModelo
from app.schemas.contratos.importacao import PreviaImportacaoModelo
from app.services.contratos import servico_configuracao_execucao as configuracao
from app.services.contratos import servico_importacao_modelos_xlsx as servico
from app.services.contratos.servico_importacao_xlsx import TAMANHO_MAXIMO, ErroPlanilha

roteador = APIRouter(prefix="/contratos", tags=["Contratos: importação de modelos por XLSX"], responses=RESPOSTAS_AUTENTICADAS)

# Slug do recurso próprio na ACL (criado pela migração, liberado pelo SuperRoot)
RECURSO = "importacao-modelos"
pode_importar = exigir_acl(RECURSO, NivelAcl.MODIFICACAO)
super_root = exigir_papeis(Papel.SUPER_ROOT)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NAO_ENCONTRADO = resposta_nao_encontrado("Contrato")

ARQUIVO_INVALIDO = {
    status.HTTP_400_BAD_REQUEST: {
        "model": RespostaErro,
        "description": "Arquivo vazio, acima de 5 MB ou que não é .xlsx (`invalido`). Na importação, também quando a planilha tem "
        "erros: o corpo traz `erros` com `linha`, `campo` e `mensagem` e nada é gravado.",
    }
}
RESPOSTA_MODELO = {status.HTTP_200_OK: {"content": {XLSX: {}}, "description": "Planilha modelo."}}


def _acesso_contrato(usuario: Usuario = Depends(pode_importar), _: Usuario = Depends(pode_modificar)) -> Usuario:
    """Junta as duas exigências de ACL (importação e edição de contratos) numa dependência só."""
    return usuario


def _acesso_global(usuario: Usuario = Depends(pode_importar), _: Usuario = Depends(super_root)) -> Usuario:
    """Modelos globais: ACL de importação e papel SuperRoot."""
    return usuario


async def _conteudo(arquivo: UploadFile) -> bytes:
    """Lê o arquivo enviado; só aceita a extensão .xlsx."""
    if not (arquivo.filename or "").lower().endswith(".xlsx"):
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "Envie a planilha no formato .xlsx.", "invalido")
    return await arquivo.read(TAMANHO_MAXIMO + 1)


def _modelo(tipo: str) -> Response:
    """Planilha modelo (gerada na hora) do tipo pedido."""
    gerar = servico.gerar_modelo_checklist if tipo == "checklist" else servico.gerar_modelo_formulario
    return Response(gerar(), media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="modelo-importacao-{tipo}.xlsx"'})


def _erro_planilha(erro: ErroPlanilha) -> ErroApi:
    """Erros da planilha vão na resposta, com linha e campo, para a tela listar."""
    return ErroApi(status.HTTP_400_BAD_REQUEST, str(erro), "invalido", erros=[e.model_dump() for e in erro.erros])


# ---------------------------------------------------------------------------------------------
# No contrato
# ---------------------------------------------------------------------------------------------

@roteador.get("/{contrato_id}/{recurso}/importacao-xlsx/modelo", response_class=Response, summary="Baixar a planilha modelo (checklist ou formulário)",
              description="`recurso` = `checklists` ou `formularios`. Exige ACL `importacao-modelos` e `contratos` ≥ MODIFICACAO.",
              responses=RESPOSTA_MODELO)
def baixar_modelo_contrato(contrato_id: uuid.UUID, recurso: Literal["checklists", "formularios"], _: Usuario = Depends(_acesso_contrato)) -> Response:
    """Entrega o modelo; não depende do contrato."""
    return _modelo("checklist" if recurso == "checklists" else "formulario")


@roteador.post("/{contrato_id}/{recurso}/importacao-xlsx/previa", response_model=PreviaImportacaoModelo,
               summary="Prévia da importação de checklist ou formulário",
               description="`multipart/form-data` com a planilha em `arquivo`. Lê e valida sem gravar: devolve o que foi lido, os erros "
               "(com a linha) e os avisos. Exige ACL `importacao-modelos` e `contratos` ≥ MODIFICACAO.",
               responses={**ARQUIVO_INVALIDO, **NAO_ENCONTRADO})
async def previa_contrato(contrato_id: uuid.UUID, recurso: Literal["checklists", "formularios"], arquivo: UploadFile = File(..., description="Planilha .xlsx"),
                          sessao: Session = Depends(obter_sessao), _: Usuario = Depends(_acesso_contrato)) -> PreviaImportacaoModelo:
    """Prévia: nada é gravado."""
    conteudo = await _conteudo(arquivo)
    with traduzir_erros():
        return servico.previa("checklist" if recurso == "checklists" else "formulario", conteudo)


@roteador.post("/{contrato_id}/checklists/importacao-xlsx", response_model=list[LeituraChecklist], status_code=status.HTTP_201_CREATED,
               summary="Importar checklist da planilha (versão inativa)",
               description="`multipart/form-data` com a mesma planilha da prévia. Valida de novo e, sem erros, cria uma versão **inativa** do "
               "checklist; devolve a lista de versões. Exige ACL `importacao-modelos`, `contratos` ≥ MODIFICACAO e poder editar o contrato.",
               responses={**ARQUIVO_INVALIDO, **NAO_ENCONTRADO, **SEM_VINCULO})
async def importar_checklist(contrato_id: uuid.UUID, arquivo: UploadFile = File(..., description="Planilha .xlsx"),
                             sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(_acesso_contrato)):
    """Cria a versão do checklist a partir da planilha."""
    conteudo = await _conteudo(arquivo)
    try:
        with traduzir_erros(sessao):
            servico.importar_no_contrato(sessao, "checklist", contrato_id, conteudo, arquivo.filename or "planilha.xlsx", autor)
            return configuracao.listar_checklists(sessao, contrato_id)
    except ErroPlanilha as erro:
        raise _erro_planilha(erro) from erro


@roteador.post("/{contrato_id}/formularios/importacao-xlsx", response_model=list[LeituraFormulario], status_code=status.HTTP_201_CREATED,
               summary="Importar formulário de avaliação da planilha (versão inativa)",
               description="`multipart/form-data` com a mesma planilha da prévia. Valida de novo e, sem erros, cria uma versão **inativa** do "
               "formulário; devolve a lista de versões. Exige ACL `importacao-modelos`, `contratos` ≥ MODIFICACAO e poder editar o contrato.",
               responses={**ARQUIVO_INVALIDO, **NAO_ENCONTRADO, **SEM_VINCULO})
async def importar_formulario(contrato_id: uuid.UUID, arquivo: UploadFile = File(..., description="Planilha .xlsx"),
                              sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(_acesso_contrato)):
    """Cria a versão do formulário a partir da planilha."""
    conteudo = await _conteudo(arquivo)
    try:
        with traduzir_erros(sessao):
            servico.importar_no_contrato(sessao, "formulario", contrato_id, conteudo, arquivo.filename or "planilha.xlsx", autor)
            return configuracao.listar_formularios(sessao, contrato_id)
    except ErroPlanilha as erro:
        raise _erro_planilha(erro) from erro


# ---------------------------------------------------------------------------------------------
# Modelos globais
# ---------------------------------------------------------------------------------------------

@roteador.get("/modelos/importacao-xlsx/{tipo}/modelo", response_class=Response, summary="Baixar a planilha modelo de um modelo global",
              description="`tipo` = `checklist` ou `formulario`. Exige ACL `importacao-modelos` e papel SuperRoot.", responses=RESPOSTA_MODELO)
def baixar_modelo_global(tipo: Literal["checklist", "formulario"], _: Usuario = Depends(_acesso_global)) -> Response:
    """Entrega o modelo da planilha."""
    return _modelo(tipo)


@roteador.post("/modelos/importacao-xlsx/{tipo}/previa", response_model=PreviaImportacaoModelo, summary="Prévia da importação de modelo global",
               description="`multipart/form-data` com a planilha em `arquivo`. Não grava nada. Exige ACL `importacao-modelos` e papel SuperRoot.",
               responses=ARQUIVO_INVALIDO)
async def previa_global(tipo: Literal["checklist", "formulario"], arquivo: UploadFile = File(..., description="Planilha .xlsx"),
                        _: Usuario = Depends(_acesso_global)) -> PreviaImportacaoModelo:
    """Prévia de um modelo global."""
    conteudo = await _conteudo(arquivo)
    with traduzir_erros():
        return servico.previa(tipo, conteudo)


@roteador.post("/modelos/importacao-xlsx/{tipo}", response_model=LeituraModelo, status_code=status.HTTP_201_CREATED,
               summary="Importar modelo global da planilha",
               description="`multipart/form-data` com a mesma planilha da prévia. Valida de novo e, sem erros, cria o modelo global. "
               "Exige ACL `importacao-modelos` e papel SuperRoot.", responses=ARQUIVO_INVALIDO)
async def importar_global(tipo: Literal["checklist", "formulario"], arquivo: UploadFile = File(..., description="Planilha .xlsx"),
                          sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(_acesso_global)) -> LeituraModelo:
    """Cria o modelo global a partir da planilha."""
    conteudo = await _conteudo(arquivo)
    try:
        with traduzir_erros(sessao):
            return configuracao.leitura_modelo(servico.importar_como_modelo(sessao, tipo, conteudo, arquivo.filename or "planilha.xlsx", autor))
    except ErroPlanilha as erro:
        raise _erro_planilha(erro) from erro
