"""
===============================================================================
ARQUIVO: rotas.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Roteador principal: reúne os roteadores de cada assunto (um arquivo por assunto
em routes/) num único APIRouter.

RESUMO TÉCNICO:
Importa os módulos de app/api/routes e de app/api/routes/contratos e inclui o
roteador de cada um em roteador_api. A ordem de inclusão importa quando dois
caminhos podem coincidir: caminhos fixos (ex.: /contratos/empresas,
/chamados/painel) vêm antes dos que têm parâmetro (/contratos/{contrato_id},
/chamados/{numero}).

FINALIDADE DE NEGÓCIO:
É o mapa de todos os módulos que o SGI SPI expõe: portal, RH, tarefas,
protocolo, patrimônio, chamados, rede, contratos e integrações. Módulo novo só
fica acessível depois de incluído aqui.

CONTEXTO NO SISTEMA:
O app/main.py inclui roteador_api com o prefixo /api. O teste
test_openapi_documenta_endpoints confere a documentação das rotas reunidas.

===============================================================================
"""

from fastapi import APIRouter

from app.api.routes import acl, assinatura_email, backup, autenticacao, atalhos, menu, busca, chamados, chamados_glpi, chamados_migracao, chamados_painel, chamados_qualidade, contratacoes, documentacao, diretorio, favoritos, integracao_bookstack, integracao_glpi, integracao_sigeo, ldap, manuais, melhorias, sla, painel_executivo, notificacoes, notificacoes_changelog, notificacoes_cliente_windows, notificacoes_preferencias, noticias, patrimonio, preferencias, protocolo, rede, reserva_espacos, rh, rh_admissao, rh_cargos, rh_pessoal, rh_pre_cadastro, tarefas, saude, setores, smtp, usuarios, versoes
from app.api.routes.contratos import alteracoes, portarias, contratos, correcoes, diario, empresas, execucao, exportacao, importacao, importacao_modelos, migracao, modelos, orcamento, parametros as parametros_contratos, rascunhos, relatorios

# APIRouter é um "grupo de rotas" do FastAPI; include_router copia as rotas de cada
# arquivo para este grupo. O FastAPI testa as rotas na ordem em que foram incluídas,
# por isso caminhos fixos precisam vir antes dos que têm parâmetro ({id}).
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
roteador_api.include_router(parametros_contratos.roteador)
roteador_api.include_router(migracao.roteador)
roteador_api.include_router(importacao.roteador)
roteador_api.include_router(importacao_modelos.roteador)
roteador_api.include_router(exportacao.roteador)
roteador_api.include_router(busca.roteador)
roteador_api.include_router(favoritos.roteador)
roteador_api.include_router(chamados_glpi.roteador)
# O do painel vem antes: `/chamados/painel` e `/chamados/eventos` não podem cair em `/chamados/{numero}`
roteador_api.include_router(chamados_painel.roteador)
roteador_api.include_router(chamados_qualidade.roteador)
roteador_api.include_router(chamados_migracao.roteador)
roteador_api.include_router(chamados.roteador)
roteador_api.include_router(rede.roteador)
roteador_api.include_router(atalhos.roteador)
roteador_api.include_router(menu.roteador)
roteador_api.include_router(integracao_glpi.roteador)
roteador_api.include_router(integracao_sigeo.roteador)
roteador_api.include_router(backup.roteador)
roteador_api.include_router(versoes.roteador)
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
