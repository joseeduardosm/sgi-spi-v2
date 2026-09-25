import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.rotas import roteador_api
from app.core.banco import FabricaSessao
from app.core.configuracao import obter_configuracao
from app.core.erros import (
    CABECALHO_CORRELACAO,
    ErroApi,
    middleware_correlacao,
    tratar_erro_api,
    tratar_erro_http,
    tratar_erro_inesperado,
    tratar_erro_validacao,
)
from app.services.agendador_ldap import AgendadorSincronizacaoLdap
from app.services.servico_usuarios import garantir_conta_admin

config = obter_configuracao()
prefixo = config.prefixo_api
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
    with FabricaSessao() as sessao:
        garantir_conta_admin(sessao)
    agendador = AgendadorSincronizacaoLdap()
    agendador.iniciar()
    yield
    agendador.parar()


app = FastAPI(
    title="API contratos-spi",
    version=config.versao_aplicacao,
    description=(
        "API do sistema de gestão de contratos da Secretaria de Parcerias em Investimentos.\n\n"
        "Autenticação: obtenha um token em `POST /api/autenticacao/login` e envie-o em "
        "`Authorization: Bearer <token>`. Erros seguem o formato `{\"detalhe\": ..., \"codigo\": ...}`. "
        "Documentação textual completa em `docs/` no repositório."
    ),
    openapi_url=f"{prefixo}/openapi.json",
    docs_url=f"{prefixo}/documentacao",
    redoc_url=f"{prefixo}/redoc",
    lifespan=ciclo_de_vida,
)

if config.origens_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.origens_cors,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[CABECALHO_CORRELACAO],
    )

app.middleware("http")(middleware_correlacao)
app.add_exception_handler(ErroApi, tratar_erro_api)
app.add_exception_handler(StarletteHTTPException, tratar_erro_http)
app.add_exception_handler(RequestValidationError, tratar_erro_validacao)
app.add_exception_handler(Exception, tratar_erro_inesperado)
app.include_router(roteador_api, prefix=prefixo)
