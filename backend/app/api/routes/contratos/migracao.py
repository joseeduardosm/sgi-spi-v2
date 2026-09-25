"""Importação do Módulo de Contratos do SGI SPI (`/api/contratos/migracao-sgi`). Restrita ao SuperRoot."""

from fastapi import APIRouter, Depends, status

from app.api.dependencias import exigir_papeis
from app.api.respostas import RESPOSTAS_AUTENTICADAS
from app.core.erros import ErroApi
from app.models.usuario import Papel, Usuario
from app.schemas.comum import RespostaErro
from app.schemas.contratos.migracao import EstadoMigracaoSgi, InicioMigracaoSgi
from app.services.contratos import servico_migracao_sgi as servico

roteador = APIRouter(prefix="/contratos/migracao-sgi", tags=["Contratos: importação do SGI"], responses=RESPOSTAS_AUTENTICADAS)
super_root = exigir_papeis(Papel.SUPER_ROOT)


@roteador.get("", response_model=EstadoMigracaoSgi, summary="Estado da importação do SGI",
              description="Situação, etapa, resultado e últimas linhas do registro da última importação. Restrito ao SuperRoot.")
def estado_migracao(_: Usuario = Depends(super_root)):
    return servico.ler_estado()


@roteador.post(
    "",
    response_model=EstadoMigracaoSgi,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Importar os contratos do SGI",
    description=(
        "Confere as senhas por SSH (origem: usuário do SGI, que também precisa do sudo lá; destino: usuário deste servidor) "
        "e inicia em segundo plano a extração somente leitura e a carga. A carga **substitui** todos os dados do módulo "
        "(contratos, empresas, anexos). Acompanhe por `GET`. As senhas não são gravadas. Restrito ao SuperRoot."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": RespostaErro, "description": "Senha incorreta ou recusada pelo sudo (`senha_invalida`)."},
        status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Já existe uma importação em andamento (`conflito`)."},
        status.HTTP_502_BAD_GATEWAY: {"model": RespostaErro, "description": "Servidor inacessível por SSH (`servidor_inacessivel`)."},
    },
)
def iniciar_migracao(dados: InicioMigracaoSgi, autor: Usuario = Depends(super_root)):
    try:
        return servico.iniciar(dados.senha_origem, dados.senha_destino, autor)
    except servico.ErroMigracao as erro:
        raise ErroApi(erro.status_code, str(erro), erro.codigo) from erro
