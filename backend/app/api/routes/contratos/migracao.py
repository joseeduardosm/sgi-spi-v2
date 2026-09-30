# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de importação dos dados do SGI SPI (SuperRoot).
"""Importação do Módulo de Contratos do SGI SPI (`/api/contratos/migracao-sgi`).

- `POST /rascunho` (conta root): lê um contrato no SGI e devolve o rascunho do cadastro; **nada é gravado**. A tela
  abre o formulário de novo contrato preenchido, e o usuário revisa e salva pelo `POST /api/contratos`.
- `GET`/`POST ""` (SuperRoot): importação completa do módulo (substitui todos os dados), não usada pela tela.

A importação roda em segundo plano (pode levar minutos por causa dos anexos): o `POST` só confere
as senhas e dispara o processo; a tela acompanha o andamento consultando o `GET`.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_conta_root, exigir_papeis
from app.api.respostas import RESPOSTAS_AUTENTICADAS
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.usuario import Papel, Usuario
from app.schemas.comum import RespostaErro
from app.schemas.contratos.migracao import EstadoMigracaoSgi, InicioMigracaoSgi, PedidoRascunhoSgi, RascunhoContratoSgi
from app.services.contratos import servico_migracao_sgi as servico

roteador = APIRouter(prefix="/contratos/migracao-sgi", tags=["Contratos: importação do SGI"], responses=RESPOSTAS_AUTENTICADAS)
super_root = exigir_papeis(Papel.SUPER_ROOT)


@roteador.get("", response_model=EstadoMigracaoSgi, summary="Estado da importação do SGI",
              description="Situação, etapa, resultado e últimas linhas do registro da última importação. Restrito ao SuperRoot.")
def estado_migracao(_: Usuario = Depends(super_root)):
    """Estado da última importação (situação, etapa atual, resultado e trecho do registro)."""
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
    """Valida as senhas e inicia a importação; erros conhecidos do serviço viram 400/409/502."""
    try:
        return servico.iniciar(dados.senha_origem, dados.senha_destino, autor)
    except servico.ErroMigracao as erro:
        raise ErroApi(erro.status_code, str(erro), erro.codigo) from erro


@roteador.post(
    "/rascunho",
    response_model=RascunhoContratoSgi,
    summary="Rascunho de um contrato do SGI (conta root)",
    description=(
        "Lê no SGI, **somente leitura**, o contrato `numero` (cabeçalho, empresa, prepostos ativos, itens e equipe vigente) e devolve os "
        "dados prontos para o formulário de novo contrato. **Nada é gravado**: o usuário revisa e salva pelo `POST /api/contratos`. "
        "A equipe é convertida para os usuários daqui (login ou id do AD); quem não tem conta ativa fica de fora, com aviso. "
        "A senha do SSH do SGI (também usada no sudo de lá) não é gravada. Restrito à conta root."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": RespostaErro, "description": "Senha do SGI incorreta ou recusada pelo sudo (`senha_invalida`)."},
        status.HTTP_404_NOT_FOUND: {"model": RespostaErro, "description": "Contrato não encontrado no SGI (`nao_encontrado`)."},
        status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "O contrato já está cadastrado aqui (`conflito`)."},
        status.HTTP_502_BAD_GATEWAY: {"model": RespostaErro, "description": "SGI inacessível ou falha na leitura (`servidor_inacessivel`, `sgi_indisponivel`)."},
    },
)
def rascunho_sgi(dados: PedidoRascunhoSgi, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(exigir_conta_root)):
    """Monta o rascunho do contrato a partir do SGI (erros conhecidos viram 400/404/409/502)."""
    try:
        return servico.rascunho_contrato(sessao, dados.numero, dados.senha_origem)
    except servico.ErroMigracao as erro:
        raise ErroApi(erro.status_code, str(erro), erro.codigo) from erro
