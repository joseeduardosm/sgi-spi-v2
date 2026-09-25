"""Respostas de erro padronizadas, reutilizadas pelas rotas e pelo OpenAPI."""

from fastapi import status

from app.core.erros import ErroApi
from app.schemas.comum import RespostaErro, RespostaErroAcl, RespostaErroValidacao


def erro_regra(mensagem: str, conflito: bool) -> ErroApi:
    """Regra de negócio violada: 409 (conflito/duplicidade) ou 400 (operação inválida)."""
    if conflito:
        return ErroApi(status.HTTP_409_CONFLICT, mensagem, "conflito")
    return ErroApi(status.HTTP_400_BAD_REQUEST, mensagem, "invalido")


def nao_encontrado(o_que: str) -> ErroApi:
    return ErroApi(status.HTTP_404_NOT_FOUND, f"{o_que} não encontrado.", "nao_encontrado")


VALIDACAO = {status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": RespostaErroValidacao, "description": "Dados inválidos (`codigo = validacao`)."}}

RESPOSTAS_AUTENTICADAS = {
    **VALIDACAO,
    status.HTTP_401_UNAUTHORIZED: {"model": RespostaErro, "description": "Não autenticado (`codigo = nao_autenticado`)."},
    status.HTTP_403_FORBIDDEN: {
        "model": RespostaErroAcl,
        "description": "Perfil pendente (`revisao_perfil_obrigatoria`), ACL insuficiente (`acl_negado`) ou papel exigido ausente (`acesso_negado`).",
    },
}


def resposta_nao_encontrado(o_que: str) -> dict:
    return {status.HTTP_404_NOT_FOUND: {"model": RespostaErro, "description": f"{o_que} não encontrado (`codigo = nao_encontrado`)."}}


INVALIDO = {status.HTTP_400_BAD_REQUEST: {"model": RespostaErro, "description": "Regra de negócio violada (`codigo = invalido`)."}}
CONFLITO = {status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Registro duplicado (`codigo = conflito`)."}}
