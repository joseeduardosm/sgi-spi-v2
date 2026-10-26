# Criado por José Eduardo Santana Martins
# Este arquivo serve para reunir todos os roteadores da API sob o prefixo /api.
"""Roteador principal: junta os roteadores de cada assunto (um arquivo por assunto em `routes/`).

O `main.py` inclui este roteador com o prefixo /api. A ordem de inclusão importa quando dois
caminhos podem coincidir (ver comentário abaixo).
"""

from fastapi import APIRouter

from app.api.routes import acl, assinatura_email, autenticacao, atalhos, menu, busca, chamados, contratacoes, documentacao, diretorio, favoritos, integracao_bookstack, integracao_glpi, integracao_sigeo, ldap, manuais, melhorias, sla, painel_executivo, notificacoes, notificacoes_changelog, notificacoes_cliente_windows, notificacoes_preferencias, noticias, patrimonio, preferencias, protocolo, reserva_espacos, rh, rh_admissao, rh_cargos, rh_pessoal, rh_pre_cadastro, tarefas, saude, setores, smtp, usuarios
from app.api.routes.contratos import alteracoes, portarias, contratos, correcoes, diario, empresas, execucao, exportacao, importacao, importacao_modelos, migracao, modelos, orcamento, rascunhos, relatorios

roteador_api = APIRouter()
# Módulos do portal: saúde, autenticação, usuários, setores, ACL, diretórios LDAP e servidores SMTP
roteador_api.include_router(saude.roteador)
roteador_api.include_router(documentacao.roteador)
roteador_api.include_router(autenticacao.roteador)
roteador_api.include_router(usuarios.roteador)
roteador_api.include_router(setores.roteador)
roteador_api.include_router(acl.roteador)
roteador_api.include_router(ldap.roteador)
roteador_api.include_router(smtp.roteador)
roteador_api.include_router(notificacoes_changelog.roteador)
roteador_api.include_router(notificacoes_preferencias.roteador)
roteador_api.include_router(notificacoes.roteador)
roteador_api.include_router(notificacoes_cliente_windows.roteador)
roteador_api.include_router(rh.roteador)
roteador_api.include_router(rh_cargos.roteador)
roteador_api.include_router(rh_pre_cadastro.roteador)
roteador_api.include_router(rh_admissao.roteador)
roteador_api.include_router(rh_pessoal.roteador)
roteador_api.include_router(tarefas.roteador)
roteador_api.include_router(noticias.roteador)
roteador_api.include_router(melhorias.roteador)
roteador_api.include_router(sla.roteador)
roteador_api.include_router(diretorio.roteador)
roteador_api.include_router(painel_executivo.roteador)
roteador_api.include_router(assinatura_email.roteador)
roteador_api.include_router(protocolo.roteador)
roteador_api.include_router(patrimonio.roteador)
roteador_api.include_router(preferencias.roteador)
roteador_api.include_router(reserva_espacos.roteador)
roteador_api.include_router(contratacoes.roteador)
# Módulo de contratos
# Caminhos fixos antes de contratos: `/contratos/empresas` não pode cair em `/contratos/{contrato_id}`
roteador_api.include_router(empresas.roteador)
roteador_api.include_router(modelos.roteador)
roteador_api.include_router(migracao.roteador)
roteador_api.include_router(importacao.roteador)
roteador_api.include_router(importacao_modelos.roteador)
roteador_api.include_router(exportacao.roteador)
roteador_api.include_router(busca.roteador)
roteador_api.include_router(favoritos.roteador)
roteador_api.include_router(chamados.roteador)
roteador_api.include_router(atalhos.roteador)
roteador_api.include_router(menu.roteador)
roteador_api.include_router(integracao_glpi.roteador)
roteador_api.include_router(integracao_sigeo.roteador)
roteador_api.include_router(integracao_bookstack.roteador)
roteador_api.include_router(manuais.roteador)
roteador_api.include_router(relatorios.roteador)
roteador_api.include_router(relatorios.roteador_painel)
roteador_api.include_router(contratos.roteador)
# Rotas dentro de um contrato (/contratos/{contrato_id}/...)
roteador_api.include_router(orcamento.roteador)
roteador_api.include_router(execucao.roteador)
roteador_api.include_router(alteracoes.roteador)
roteador_api.include_router(portarias.roteador)
roteador_api.include_router(correcoes.roteador)
roteador_api.include_router(diario.roteador)
roteador_api.include_router(rascunhos.roteador)
