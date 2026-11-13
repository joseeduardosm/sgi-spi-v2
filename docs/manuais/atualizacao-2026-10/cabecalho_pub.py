"""
===============================================================================
ARQUIVO: cabecalho_pub.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Reunir as funções comuns de publicação no BookStack (instrucoes.spi.sp.gov.br)
usadas pela atualização dos manuais de outubro de 2026.

RESUMO TÉCNICO:
Lê o token da API do arquivo token.txt (temporário, criado só para a
publicação) e oferece: `api` (chamada HTTP JSON autenticada), `pagina`
(lê uma página), funções que localizam um parágrafo/título/tabela pelo texto
e inserem, antes ou depois, ou substituem um bloco HTML, e `salvar` (grava a
página; com a variável DRY definida, só escreve dry-<id>.html para conferir).
Não é rodado sozinho: o publicar_final.py o executa com exec().

FINALIDADE DE NEGÓCIO:
Permite atualizar os manuais do SGI SPI publicados para os servidores da SPI
mexendo só nos trechos que mudaram, sem redigitar as páginas inteiras.

CONTEXTO NO SISTEMA:
Ferramenta de documentação, fora do sistema (não é usada pela API nem pelo
frontend). Usado por publicar_final.py, junto com textos_novos.py.

===============================================================================
"""

import json, re, sys, urllib.request

# Endereço da API do BookStack e token lido do arquivo (nunca gravado no código).
BASE = "https://instrucoes.spi.sp.gov.br/api"
TOKEN = open("token.txt").read().strip()


def api(metodo, caminho, corpo=None):
    """Chama a API do BookStack (método, caminho e corpo JSON opcional) e devolve a resposta já decodificada."""
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(BASE + caminho, data=dados, method=metodo,
                                 headers={"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def pagina(i):
    """Lê a página `i` do BookStack (o HTML fica na chave 'html')."""
    return api("GET", f"/pages/{i}")


def inicio_do_paragrafo(h, marcador):
    """Posição em `h` onde começa o bloco (parágrafo, título ou tabela) que contém `marcador`; falha se o texto não existir."""
    k = h.find(marcador)
    assert k >= 0, f"marcador não achado: {marcador}"
    # início da tag <p, <li ou <h que contém o marcador
    return max(h.rfind("<p", 0, k), h.rfind("<h2", 0, k), h.rfind("<h3", 0, k), h.rfind("<table", 0, k))


def fim_do_bloco(h, k):
    """Posição logo depois do fechamento da tag que abre em `k` (ex.: o </p> do parágrafo)."""
    # fim do parágrafo/lista/tabela que começa em k
    tag = re.match(r"<(\w+)", h[k:]).group(1)
    return h.index(f"</{tag}>", k) + len(tag) + 3


def inserir_depois(h, marcador, novo):
    """Insere o HTML `novo` logo depois do bloco que contém `marcador`."""
    k = inicio_do_paragrafo(h, marcador)
    f = fim_do_bloco(h, k)
    return h[:f] + "\n" + novo + h[f:]


def inserir_antes(h, marcador, novo):
    """Insere o HTML `novo` logo antes do bloco que contém `marcador`."""
    k = inicio_do_paragrafo(h, marcador)
    return h[:k] + novo + "\n" + h[k:]


def substituir_bloco(h, marcador, novo):
    """Troca o bloco que contém `marcador` pelo HTML `novo`."""
    k = inicio_do_paragrafo(h, marcador)
    f = fim_do_bloco(h, k)
    return h[:k] + novo + h[f:]


def salvar(i, html, nota):
    """Grava a página `i` no BookStack; com a variável de ambiente DRY, só salva o HTML em arquivo local (simulação)."""
    import os
    if os.environ.get("DRY"):
        open(f"dry-{i}.html", "w").write(html); print("(simulação)", i, nota); return
    api("PUT", f"/pages/{i}", {"html": html})
    print("atualizada", i, nota)


