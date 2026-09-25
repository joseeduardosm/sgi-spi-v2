# Criado por José Eduardo Santana Martins
# Este arquivo serve para reunir todos os roteadores da API sob o prefixo /api.

from fastapi import APIRouter

from app.api.routes import acl, autenticacao, ldap, saude, setores, usuarios
from app.api.routes.contratos import alteracoes, contratos, empresas, execucao, migracao, modelos, orcamento, relatorios

roteador_api = APIRouter()
roteador_api.include_router(saude.roteador)
roteador_api.include_router(autenticacao.roteador)
roteador_api.include_router(usuarios.roteador)
roteador_api.include_router(setores.roteador)
roteador_api.include_router(acl.roteador)
roteador_api.include_router(ldap.roteador)
# Caminhos fixos antes de contratos: `/contratos/empresas` não pode cair em `/contratos/{contrato_id}`
roteador_api.include_router(empresas.roteador)
roteador_api.include_router(modelos.roteador)
roteador_api.include_router(migracao.roteador)
roteador_api.include_router(relatorios.roteador)
roteador_api.include_router(relatorios.roteador_painel)
roteador_api.include_router(contratos.roteador)
roteador_api.include_router(orcamento.roteador)
roteador_api.include_router(execucao.roteador)
roteador_api.include_router(alteracoes.roteador)
