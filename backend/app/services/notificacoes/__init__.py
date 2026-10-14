# Criado por José Eduardo Santana Martins
# Este arquivo serve para reunir o serviço de Notificações (caixa, catálogo, preferências, despacho e navegador) sob um nome só.
"""Serviço de Notificações.

Os outros módulos usam `from app.services import notificacoes` e chamam `notificacoes.notificar(..., evento=<chave do catálogo>)` e
`notificacoes.encerrar(...)`. Submódulos: `caixa` (entregas e ciência), `catalogo` (eventos), `preferencias` (canais por usuário),
`despacho` (e-mail e navegador depois do commit) e `navegador` (Web Push).

Este pacote não se confunde com `app.services.contratos.servico_notificacoes`, que envia os e-mails de fluxo do módulo Contratos.
"""

from app.services.notificacoes import catalogo, despacho, layout_email, navegador, preferencias  # noqa: F401
from app.services.notificacoes.caixa import *  # noqa: F401,F403
