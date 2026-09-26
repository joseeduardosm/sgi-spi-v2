# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de importação de contrato por planilha XLSX.
"""Importação de contrato por planilha XLSX (`/api/contratos/importacao-xlsx`).

Fluxo da tela: baixar o modelo → preencher → enviar para a prévia → conferir erros e avisos →
confirmar (o mesmo arquivo é enviado de novo e só então gravado).

Acesso: ACL `importacao-contratos` ≥ MODIFICACAO (recurso liberado por usuário ou setor na tela de
ACL) **e** ACL `contratos` ≥ MODIFICACAO (quem importa precisa poder cadastrar contratos).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl
from app.api.respostas import RESPOSTAS_AUTENTICADAS
from app.api.routes.contratos.comum import pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.schemas.comum import RespostaErro
from app.schemas.contratos.contratos import DetalheContrato
from app.schemas.contratos.importacao import PreviaImportacao
from app.services.contratos import servico_contratos
from app.services.contratos import servico_importacao_xlsx as servico

roteador = APIRouter(prefix="/contratos/importacao-xlsx", tags=["Contratos: importação por XLSX"], responses=RESPOSTAS_AUTENTICADAS)

# Slug do recurso próprio da importação na ACL (criado pela migração, liberado pelo SuperRoot)
RECURSO = "importacao-contratos"
pode_importar = exigir_acl(RECURSO, NivelAcl.MODIFICACAO)
MODELO = Path(__file__).resolve().parents[3] / "recursos" / "modelo-importacao-contrato.xlsx"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

ARQUIVO_INVALIDO = {
    status.HTTP_400_BAD_REQUEST: {
        "model": RespostaErro,
        "description": "Arquivo vazio, acima de 5 MB ou que não é .xlsx (`invalido`). Na importação, também quando a planilha tem "
        "erros: o corpo traz `erros` com `linha`, `campo` e `mensagem` e nada é gravado.",
    }
}


def _exigir_acessos(usuario: Usuario = Depends(pode_importar), _: Usuario = Depends(pode_modificar)) -> Usuario:
    """Junta as duas exigências de ACL (importação e cadastro de contratos) numa dependência só."""
    return usuario


async def _conteudo(arquivo: UploadFile) -> bytes:
    """Lê o arquivo enviado; só aceita a extensão .xlsx (o formato antigo .xls não é lido)."""
    if not (arquivo.filename or "").lower().endswith(".xlsx"):
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "Envie a planilha no formato .xlsx.", "invalido")
    return await arquivo.read(servico.TAMANHO_MAXIMO + 1)


@roteador.get(
    "/modelo",
    response_class=FileResponse,
    summary="Baixar o modelo da planilha",
    description="Planilha em branco \"Checklist de Alimentação do Sistema de Contratos\". Exige ACL `importacao-contratos` e "
    "`contratos` ≥ MODIFICACAO.",
    responses={status.HTTP_200_OK: {"content": {XLSX: {}}, "description": "Planilha modelo."}},
)
def baixar_modelo(_: Usuario = Depends(_exigir_acessos)) -> FileResponse:
    """Entrega o modelo guardado em `app/recursos`."""
    return FileResponse(MODELO, media_type=XLSX, filename="modelo-importacao-contrato.xlsx")


@roteador.post(
    "/previa",
    response_model=PreviaImportacao,
    summary="Prévia da importação",
    description="`multipart/form-data` com a planilha em `arquivo`. Lê e valida sem gravar nada: devolve os dados convertidos, "
    "a empresa (existente, reaproveitada sem alteração, ou nova), o preposto, os itens, os erros (com a linha) e os avisos. "
    "Exige ACL `importacao-contratos` e `contratos` ≥ MODIFICACAO.",
    responses=ARQUIVO_INVALIDO,
)
async def previa(arquivo: UploadFile = File(..., description="Planilha .xlsx"), sessao: Session = Depends(obter_sessao),
                 _: Usuario = Depends(_exigir_acessos)) -> PreviaImportacao:
    """Prévia: nada é gravado; a tela mostra o resultado para o usuário conferir."""
    conteudo = await _conteudo(arquivo)
    with traduzir_erros():
        return servico.previa(sessao, conteudo)


@roteador.post(
    "",
    response_model=DetalheContrato,
    status_code=status.HTTP_201_CREATED,
    summary="Importar o contrato",
    description="`multipart/form-data` com a mesma planilha da prévia em `arquivo`. Valida de novo e, sem erros, cadastra numa "
    "única transação a empresa (se nova), o preposto (se novo) e o contrato com os itens. A equipe não é importada. "
    "Exige ACL `importacao-contratos` e `contratos` ≥ MODIFICACAO.",
    responses=ARQUIVO_INVALIDO,
)
async def importar(arquivo: UploadFile = File(..., description="Planilha .xlsx"), sessao: Session = Depends(obter_sessao),
                   autor: Usuario = Depends(_exigir_acessos)) -> DetalheContrato:
    """Grava a importação e devolve o detalhe do contrato criado."""
    conteudo = await _conteudo(arquivo)
    try:
        with traduzir_erros(sessao):
            contrato = servico.importar(sessao, conteudo, arquivo.filename or "planilha.xlsx", autor)
    except servico.ErroPlanilha as erro:
        # Erros da planilha vão na resposta, com linha e campo, para a tela listar
        raise ErroApi(status.HTTP_400_BAD_REQUEST, str(erro), "invalido",
                      erros=[e.model_dump() for e in erro.erros]) from erro
    return servico_contratos.detalhar_contrato(sessao, contrato.id, autor)
