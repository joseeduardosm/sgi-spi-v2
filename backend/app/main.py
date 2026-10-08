# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar a aplicação FastAPI, registrar rotas, middlewares e tratamento de erros.
"""Ponto de entrada da API.

O uvicorn carrega `app.main:app`. Aqui a aplicação é montada nesta ordem:
1. configuração e logs;
2. rotina de inicialização/encerramento (conta administrativa e sincronização LDAP);
3. objeto FastAPI com a documentação automática (Swagger/ReDoc);
4. CORS (opcional), middleware de correlação e tratadores de erro;
5. todas as rotas sob o prefixo /api.
"""

import logging
import os
import time
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
from app.services.agendador_aniversarios import AgendadorParabens
from app.services.agendador_ldap import AgendadorSincronizacaoLdap
from app.services.servico_usuarios import garantir_conta_admin

config = obter_configuracao()
prefixo = config.prefixo_api
# Formato das linhas de log: data, nível, origem e mensagem (vão para o journal do systemd)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
    """Executado quando a API sobe (antes do `yield`) e quando ela é encerrada (depois do `yield`)."""
    # Garante que a conta administrativa (root) exista e esteja com a senha do .env
    with FabricaSessao() as sessao:
        garantir_conta_admin(sessao)
    # Inicia a sincronização periódica dos usuários do LDAP em segundo plano
    agendador = AgendadorSincronizacaoLdap()
    agendador.iniciar()
    # Parabéns automático de aniversário (mensagem interna + e-mail, uma vez por dia)
    agendador_parabens = AgendadorParabens()
    agendador_parabens.iniciar()
    yield
    # Encerramento: para as rotinas em segundo plano
    agendador.parar()
    agendador_parabens.parar()


# Fuso do processo = São Paulo: o servidor roda em UTC e qualquer `datetime.now()` ou data/hora gravada por bibliotecas (ex.: metadados dos PDFs)
# sairia 3 horas adiantada. As datas com hora do banco continuam em UTC (ver `agora_utc`); só a exibição usa o horário de São Paulo.
os.environ["TZ"] = "America/Sao_Paulo"
if hasattr(time, "tzset"):
    time.tzset()

app = FastAPI(
    title="API SGI SPI – Sistema de Gestão Integrada",
    version=config.versao_aplicacao,
    description=(
        "API do SGI SPI (Sistema de Gestão Integrada) da Secretaria de Parcerias em Investimentos: contratos, RH, mensageria e administração.\n\n"
        "Autenticação: obtenha um token em `POST /api/autenticacao/login` e envie-o em "
        "`Authorization: Bearer <token>`. Erros seguem o formato `{\"detalhe\": ..., \"codigo\": ...}`. "
        "Documentação textual completa em `docs/` no repositório."
    ),
    # Documentação (/api/documentacao, /api/redoc e /api/openapi.json) protegida pela ACL `documentacao-api`:
    # as rotas ficam em `api/routes/documentacao.py`, por isso as automáticas do FastAPI são desligadas
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
    lifespan=ciclo_de_vida,
)

# CORS só é necessário se o frontend for servido por outro endereço; com o Nginx servindo os dois
# no mesmo endereço, a lista fica vazia e nada é liberado
if config.origens_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.origens_cors,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        # Permite ao navegador ler o código de correlação das respostas
        expose_headers=[CABECALHO_CORRELACAO, "X-Token-Renovado", "X-Token-Expira-Em"],
    )

# Código de correlação em todas as respostas
app.middleware("http")(middleware_correlacao)
# Tratadores de erro: cada tipo de exceção vira a resposta JSON padrão {"detalhe", "codigo"}
app.add_exception_handler(ErroApi, tratar_erro_api)
app.add_exception_handler(StarletteHTTPException, tratar_erro_http)
app.add_exception_handler(RequestValidationError, tratar_erro_validacao)
# Qualquer outro erro (falha inesperada) vira 500 com código de correlação
app.add_exception_handler(Exception, tratar_erro_inesperado)
# Todas as rotas ficam sob /api
app.include_router(roteador_api, prefix=prefixo)
