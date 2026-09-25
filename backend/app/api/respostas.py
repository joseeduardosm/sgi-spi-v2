# Criado por José Eduardo Santana Martins
# Este arquivo serve para padronizar as respostas de erro das rotas e a documentação delas no OpenAPI.
"""Respostas de erro padronizadas, reutilizadas pelas rotas e pelo OpenAPI.

Dois tipos de coisa moram aqui:
- funções que criam erros (`erro_regra`, `nao_encontrado`), usadas dentro das rotas;
- dicionários que descrevem os erros possíveis de cada rota (`CONFLITO`, `INVALIDO`...), passados
  no parâmetro `responses=` dos decoradores para aparecerem na documentação Swagger.
"""

from fastapi import status

from app.core.erros import ErroApi
from app.schemas.comum import RespostaErro, RespostaErroAcl, RespostaErroValidacao


def erro_regra(mensagem: str, conflito: bool) -> ErroApi:
    """Regra de negócio violada: 409 (conflito/duplicidade) ou 400 (operação inválida)."""
    if conflito:
        return ErroApi(status.HTTP_409_CONFLICT, mensagem, "conflito")
    return ErroApi(status.HTTP_400_BAD_REQUEST, mensagem, "invalido")


def nao_encontrado(o_que: str) -> ErroApi:
    """Erro 404 com mensagem do tipo "Contrato não encontrado."."""
    return ErroApi(status.HTTP_404_NOT_FOUND, f"{o_que} não encontrado.", "nao_encontrado")


# Erro 422 (dados fora do formato), presente em toda rota que recebe dados
VALIDACAO = {status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": RespostaErroValidacao, "description": "Dados inválidos (`codigo = validacao`)."}}

# Erros comuns a toda rota que exige login: 422, 401 e 403
RESPOSTAS_AUTENTICADAS = {
    **VALIDACAO,
    status.HTTP_401_UNAUTHORIZED: {"model": RespostaErro, "description": "Não autenticado (`codigo = nao_autenticado`)."},
    status.HTTP_403_FORBIDDEN: {
        "model": RespostaErroAcl,
        "description": "Perfil pendente (`revisao_perfil_obrigatoria`), ACL insuficiente (`acl_negado`) ou papel exigido ausente (`acesso_negado`).",
    },
}


def resposta_nao_encontrado(o_que: str) -> dict:
    """Descrição do 404 de uma rota, para a documentação OpenAPI."""
    return {status.HTTP_404_NOT_FOUND: {"model": RespostaErro, "description": f"{o_que} não encontrado (`codigo = nao_encontrado`)."}}


# Descrições dos erros de regra de negócio (400) e de duplicidade (409), para a documentação
INVALIDO = {status.HTTP_400_BAD_REQUEST: {"model": RespostaErro, "description": "Regra de negócio violada (`codigo = invalido`)."}}
CONFLITO = {status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Registro duplicado (`codigo = conflito`)."}}
