import json, urllib.request
API = "http://127.0.0.1:8200/api"
def chamar(m, p, tok=None, corpo=None):
    r = urllib.request.Request(API + p, data=json.dumps(corpo).encode() if corpo is not None else None, method=m,
                               headers={**({"Authorization": f"Bearer {tok}"} if tok else {}), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e: raise SystemExit(f"{m} {p} {e.code} {e.read()[:300]}")
def login(l, s="senha-lab-1"): return chamar("POST", "/autenticacao/login", corpo={"login": l, "senha": s})["token_acesso"]
def limpar_janelas(l):
    t = login(l)
    for _ in range(10):
        j = chamar("GET", "/notificacoes/resumo", t).get("janela")
        if not j: break
        chamar("POST", f"/notificacoes/{j['id']}/ciencia", t)
