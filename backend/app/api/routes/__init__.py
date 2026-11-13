"""
===============================================================================
ARQUIVO: __init__.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Marca a pasta como o pacote das rotas HTTP da API.

RESUMO TÉCNICO:
Arquivo sem código; cada módulo da pasta define um APIRouter chamado roteador
com as rotas de um assunto (ACL, chamados, contratos...).

FINALIDADE DE NEGÓCIO:
Não tem regra de negócio própria; agrupa as rotas de todos os módulos do SGI
consumidas pelo frontend Angular.

CONTEXTO NO SISTEMA:
Os roteadores são reunidos em app/api/rotas.py.

===============================================================================
"""
