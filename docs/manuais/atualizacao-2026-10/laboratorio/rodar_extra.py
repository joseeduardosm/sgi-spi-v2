import sys, os, urllib.request
sys.path.insert(0, ".")
exec(open("rodar2.py").read().split("with sync_playwright")[0].split("ID = open")[0])  # importações e helpers (cap, api, fitz, PIL)
ID = open("ids.txt").read().split()[0]
LISTA = open("lista.txt").read().strip()
def baixar(caminho, tok):
    r = urllib.request.Request(api.API + caminho, headers={"Authorization": f"Bearer {tok}"}); return urllib.request.urlopen(r, timeout=120).read()
exec("def pdf_png" + open("rodar2.py").read().split("def pdf_png")[1].split("with sync_playwright")[0])
with sync_playwright() as p:
    nav, ctx = abrir(p, 1366, 860); ctx.set_default_timeout(20000)
    pg = entrar(ctx, "marina"); pg.goto(f"{BASE}/contratos"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    foto(pg, "c01-importar-xlsx", [(pg.get_by_role("button", name="Importar XLSX"), 1, "cima")], legendas=["Importar XLSX: contratos, checklists e formulários de avaliação por planilha. Faz parte de Editar contratos: não há permissão separada"])
    nav.close()
tf = api.login("fernanda")
pdf = baixar(f"/patrimonio/classificacoes/{LISTA}/relatorio", tf)
pdf_png(pdf, 1, "i06-relatorio-pdf", [("Justificativa", 1)]); leg("i06-relatorio-pdf", ["O relatório em PDF tem as mesmas colunas do Excel; a justificativa tem coluna própria e continua na página seguinte se for longa"])
print("extra ok")
