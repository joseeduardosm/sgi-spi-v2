"""
===============================================================================
ARQUIVO: __init__.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Marca a pasta como o pacote da camada HTTP (rotas e dependências).

RESUMO TÉCNICO:
Arquivo sem código. O pacote contém dependencias.py (autenticação e
autorização), respostas.py (erros padronizados), rotas.py (roteador principal)
e a pasta routes com um arquivo por assunto.

FINALIDADE DE NEGÓCIO:
Não tem regra de negócio própria; separa a camada que recebe as requisições do
frontend da camada de serviços, onde ficam as regras.

CONTEXTO NO SISTEMA:
Usado por app/main.py, que inclui app.api.rotas.roteador_api com o prefixo
/api.

===============================================================================
"""
