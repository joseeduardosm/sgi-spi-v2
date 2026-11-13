"""
===============================================================================
ARQUIVO: __init__.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Marca a pasta backend/tests como pacote Python dos testes automatizados.

RESUMO TÉCNICO:
Arquivo sem código. Existir como pacote permite que os testes importem os
módulos de apoio (ex.: from tests.apoio_contratos import ...).

FINALIDADE DE NEGÓCIO:
Viabiliza a suíte de testes que protege as regras do SGI SPI contra
regressões a cada alteração.

CONTEXTO NO SISTEMA:
Usado pelo pytest junto com conftest.py e os arquivos apoio_*.py.

===============================================================================
"""
