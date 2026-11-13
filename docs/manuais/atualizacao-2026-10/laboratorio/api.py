"""
===============================================================================
ARQUIVO: api.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Cliente HTTP mínimo da API do laboratório dos manuais, usado pelos roteiros
de prints para preparar dados pela própria API (login, avisos etc.).

RESUMO TÉCNICO:
`chamar` monta a requisição JSON (com o token Bearer, se houver) para
http://127.0.0.1:8200/api, que o lab_web.py repassa à API do laboratório;
erro HTTP encerra o roteiro mostrando o código e o começo da resposta.
`login` devolve o token de acesso e `limpar_janelas` dá ciência às janelas
de aviso pendentes de um usuário, para elas não cobrirem as telas nos prints.

FINALIDADE DE NEGÓCIO:
Ajuda a produzir os manuais do SGI SPI com dados fictícios, sem tocar na
produção.

CONTEXTO NO SISTEMA:
Ferramenta de documentação (laboratório), fora do sistema. Importado por
rodar*.py; fala com as rotas /autenticacao/login e /notificacoes do backend.

===============================================================================
"""

import json, urllib.request
# Endereço do servidor web do laboratório, que repassa /api para a API (porta 8100).
API = "http://127.0.0.1:8200/api"
def chamar(m, p, tok=None, corpo=None):
    """Faz a chamada `m` (método) em `p` (caminho) com o token `tok` e o corpo JSON; devolve o JSON da resposta."""
    r = urllib.request.Request(API + p, data=json.dumps(corpo).encode() if corpo is not None else None, method=m,
                               headers={**({"Authorization": f"Bearer {tok}"} if tok else {}), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e: raise SystemExit(f"{m} {p} {e.code} {e.read()[:300]}")
def login(l, s="senha-lab-1"): return chamar("POST", "/autenticacao/login", corpo={"login": l, "senha": s})["token_acesso"]
def limpar_janelas(l):
    """Responde às janelas de aviso do usuário `l` (até 10), para a tela ficar limpa nos prints."""
    t = login(l)
    for _ in range(10):
        j = chamar("GET", "/notificacoes/resumo", t).get("janela")
        if not j: break
        chamar("POST", f"/notificacoes/{j['id']}/ciencia", t)
