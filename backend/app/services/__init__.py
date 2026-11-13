"""
===============================================================================
ARQUIVO: __init__.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Marcar a pasta `services` como o pacote Python das regras de negócio.

RESUMO TÉCNICO:
Arquivo vazio de propósito: só existe para que `app.services.xxx` possa ser
importado. Cada módulo do pacote (ou subpasta) cuida de um assunto.

FINALIDADE DE NEGÓCIO:
Organiza num só lugar as regras do SGI (contratos, chamados, ACL, e-mail,
LDAP etc.), separadas das rotas HTTP e dos modelos do banco.

CONTEXTO NO SISTEMA:
As rotas em `app/api/routes/` chamam os serviços deste pacote, que por sua
vez usam os modelos de `app/models/` e os schemas de `app/schemas/`.

===============================================================================
"""
