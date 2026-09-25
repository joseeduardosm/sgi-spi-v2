# Criado por José Eduardo Santana Martins
# Este arquivo serve para padronizar os erros da API no formato {"detalhe", "codigo"} com código de correlação.
"""Erros da API em pt-BR: corpo padronizado {"detalhe": ..., "codigo": ...}."""

import logging
import uuid
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Códigos padrão por status HTTP, usados quando o erro não informa um código específico
CODIGOS_PADRAO = {
    400: "invalido",
    401: "nao_autenticado",
    403: "acesso_negado",
    404: "nao_encontrado",
    405: "metodo_nao_permitido",
    409: "conflito",
    422: "validacao",
    500: "erro_interno",
    503: "servico_indisponivel",
}

# Tradução das mensagens de validação do Pydantic (pelo tipo do erro)
MENSAGENS_VALIDACAO = {
    "missing": "campo obrigatório",
    "string_too_short": "deve ter ao menos {min_length} caractere(s)",
    "string_too_long": "deve ter no máximo {max_length} caractere(s)",
    "string_pattern_mismatch": "formato inválido",
    "string_type": "deve ser um texto",
    "int_parsing": "deve ser um número inteiro",
    "int_type": "deve ser um número inteiro",
    "bool_parsing": "deve ser verdadeiro ou falso",
    "bool_type": "deve ser verdadeiro ou falso",
    "greater_than_equal": "deve ser maior ou igual a {ge}",
    "less_than_equal": "deve ser menor ou igual a {le}",
    "greater_than": "deve ser maior que {gt}",
    "literal_error": "valor inválido; permitidos: {expected}",
    "enum": "valor inválido; permitidos: {expected}",
    "uuid_parsing": "identificador inválido",
    "date_from_datetime_parsing": "data inválida (use AAAA-MM-DD)",
    "date_parsing": "data inválida (use AAAA-MM-DD)",
    "list_type": "deve ser uma lista",
    "json_invalid": "JSON inválido",
    "model_attributes_type": "objeto inválido",
    "dict_type": "objeto inválido",
}


class ErroApi(Exception):
    """Resposta de erro com `detalhe`, `codigo` e campos adicionais.

    Corpo: {"detalhe": "...", "codigo": "...", ...extras}
    """

    def __init__(self, status_code: int, detalhe: str, codigo: str, **extras: Any) -> None:
        super().__init__(detalhe)
        self.status_code = status_code
        self.detalhe = detalhe
        self.codigo = codigo
        self.extras = extras


def _cabecalhos(status_code: int, originais: dict[str, str] | None = None) -> dict[str, str] | None:
    if status_code == 401:
        return {**(originais or {}), "WWW-Authenticate": "Bearer"}
    return originais


async def tratar_erro_api(_: Request, erro: ErroApi) -> JSONResponse:
    return JSONResponse(
        {"detalhe": erro.detalhe, "codigo": erro.codigo, **erro.extras},
        status_code=erro.status_code,
        headers=_cabecalhos(erro.status_code),
    )


async def tratar_erro_http(_: Request, erro: StarletteHTTPException) -> JSONResponse:
    """HTTPException (incluindo 404/405 do roteador) no formato padrão."""
    return JSONResponse(
        {"detalhe": str(erro.detail), "codigo": CODIGOS_PADRAO.get(erro.status_code, "erro")},
        status_code=erro.status_code,
        headers=_cabecalhos(erro.status_code, getattr(erro, "headers", None)),
    )


def _mensagem_validacao(item: dict[str, Any]) -> str:
    modelo = MENSAGENS_VALIDACAO.get(item.get("type", ""))
    if modelo:
        try:
            return modelo.format(**(item.get("ctx") or {}))
        except (KeyError, IndexError):
            return modelo
    # Erros lançados pelos próprios validadores (ValueError) já vêm em pt-BR
    mensagem = str(item.get("msg", "valor inválido"))
    return mensagem.removeprefix("Value error, ")


async def tratar_erro_validacao(_: Request, erro: RequestValidationError) -> JSONResponse:
    """422 com lista de erros por campo, em pt-BR."""
    erros = []
    for item in erro.errors():
        local = [str(p) for p in item.get("loc", ()) if p not in ("body", "query", "path")]
        erros.append({"campo": ".".join(local) or None, "mensagem": _mensagem_validacao(item)})
    resumo = "; ".join(f"{e['campo']}: {e['mensagem']}" if e["campo"] else e["mensagem"] for e in erros)
    return JSONResponse(
        {"detalhe": f"Dados inválidos. {resumo}.", "codigo": "validacao", "erros": erros},
        status_code=422,
    )


CABECALHO_CORRELACAO = "X-Correlacao"
registro_log = logging.getLogger("contratos_spi.erros")


def correlacao_da_requisicao(requisicao: Request) -> str:
    """Código que identifica a requisição nos logs; exibido ao usuário para o suporte."""
    codigo = getattr(requisicao.state, "correlacao", None)
    if codigo is None:
        codigo = uuid.uuid4().hex[:12]
        requisicao.state.correlacao = codigo
    return codigo


async def middleware_correlacao(requisicao: Request, proxima):
    """Gera o código de correlação e o devolve no cabeçalho `X-Correlacao` de toda resposta."""
    codigo = correlacao_da_requisicao(requisicao)
    resposta = await proxima(requisicao)
    resposta.headers[CABECALHO_CORRELACAO] = codigo
    return resposta


async def tratar_erro_inesperado(requisicao: Request, erro: Exception) -> JSONResponse:
    """500 sem expor detalhes internos; o código de correlação liga a resposta ao log."""
    codigo = correlacao_da_requisicao(requisicao)
    registro_log.exception("Erro inesperado [%s] em %s %s", codigo, requisicao.method, requisicao.url.path, exc_info=erro)
    return JSONResponse(
        {
            "detalhe": f"Ocorreu um erro inesperado. Informe ao suporte o código {codigo}.",
            "codigo": "erro_interno",
            "correlacao": codigo,
        },
        status_code=500,
        headers={CABECALHO_CORRELACAO: codigo},
    )
