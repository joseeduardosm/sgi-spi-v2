import json, re, sys, urllib.request

BASE = "https://instrucoes.spi.sp.gov.br/api"
TOKEN = open("token.txt").read().strip()


def api(metodo, caminho, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(BASE + caminho, data=dados, method=metodo,
                                 headers={"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def pagina(i):
    return api("GET", f"/pages/{i}")


def inicio_do_paragrafo(h, marcador):
    k = h.find(marcador)
    assert k >= 0, f"marcador não achado: {marcador}"
    # início da tag <p, <li ou <h que contém o marcador
    return max(h.rfind("<p", 0, k), h.rfind("<h2", 0, k), h.rfind("<h3", 0, k), h.rfind("<table", 0, k))


def fim_do_bloco(h, k):
    # fim do parágrafo/lista/tabela que começa em k
    tag = re.match(r"<(\w+)", h[k:]).group(1)
    return h.index(f"</{tag}>", k) + len(tag) + 3


def inserir_depois(h, marcador, novo):
    k = inicio_do_paragrafo(h, marcador)
    f = fim_do_bloco(h, k)
    return h[:f] + "\n" + novo + h[f:]


def inserir_antes(h, marcador, novo):
    k = inicio_do_paragrafo(h, marcador)
    return h[:k] + novo + "\n" + h[k:]


def substituir_bloco(h, marcador, novo):
    k = inicio_do_paragrafo(h, marcador)
    f = fim_do_bloco(h, k)
    return h[:k] + novo + h[f:]


def salvar(i, html, nota):
    import os
    if os.environ.get("DRY"):
        open(f"dry-{i}.html", "w").write(html); print("(simulação)", i, nota); return
    api("PUT", f"/pages/{i}", {"html": html})
    print("atualizada", i, nota)


