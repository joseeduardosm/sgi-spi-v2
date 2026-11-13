"""
===============================================================================
ARQUIVO: __init__.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Marca a pasta app como o pacote Python da aplicação (backend do SGI SPI).

RESUMO TÉCNICO:
Arquivo sem código: sua presença permite importar os subpacotes como app.api,
app.models, app.services e app.core.

FINALIDADE DE NEGÓCIO:
Não tem regra de negócio própria; organiza o código do sistema de gestão
integrada da SPI num pacote único.

CONTEXTO NO SISTEMA:
O ponto de entrada da API é app/main.py, que monta a aplicação FastAPI a partir
dos subpacotes deste pacote.

===============================================================================
"""
