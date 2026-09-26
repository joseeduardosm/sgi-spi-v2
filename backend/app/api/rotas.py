# Criado por José Eduardo Santana Martins
# Este arquivo serve para reunir todos os roteadores da API sob o prefixo /api.
"""Roteador principal: junta os roteadores de cada assunto (um arquivo por assunto em `routes/`).

O `main.py` inclui este roteador com o prefixo /api. A ordem de inclusão importa quando dois
caminhos podem coincidir (ver comentário abaixo).
"""

from fastapi import APIRouter

from app.api.routes import acl, autenticacao, ldap, saude, setores, smtp, usuarios
from app.api.routes.contratos import alteracoes, contratos, diario, empresas, execucao, migracao, modelos, orcamento, relatorios

roteador_api = APIRouter()
# Módulos do portal: saúde, autenticação, usuários, setores, ACL, diretórios LDAP e servidores SMTP
roteador_api.include_router(saude.roteador)
roteador_api.include_router(autenticacao.roteador)
roteador_api.include_router(usuarios.roteador)
roteador_api.include_router(setores.roteador)
roteador_api.include_router(acl.roteador)
roteador_api.include_router(ldap.roteador)
roteador_api.include_router(smtp.roteador)
# Módulo de contratos
# Caminhos fixos antes de contratos: `/contratos/empresas` não pode cair em `/contratos/{contrato_id}`
roteador_api.include_router(empresas.roteador)
roteador_api.include_router(modelos.roteador)
roteador_api.include_router(migracao.roteador)
roteador_api.include_router(relatorios.roteador)
roteador_api.include_router(relatorios.roteador_painel)
roteador_api.include_router(contratos.roteador)
# Rotas dentro de um contrato (/contratos/{contrato_id}/...)
roteador_api.include_router(orcamento.roteador)
roteador_api.include_router(execucao.roteador)
roteador_api.include_router(alteracoes.roteador)
roteador_api.include_router(diario.roteador)
