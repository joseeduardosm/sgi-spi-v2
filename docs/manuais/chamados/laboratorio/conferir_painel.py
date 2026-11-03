# Criado por José Eduardo Santana Martins
# Este arquivo serve para conferir quantos chamados cabem no painel em tela cheia (TV 1920x1080), com os três tamanhos de texto.
import sys; sys.path.insert(0, ".")
from cap import *
from cliente import chamar, login
root, ana = login("root", "senha-teste"), login("ana")
cat = {c["nome"]: c["id"] for c in chamar("GET", "/chamados/parametros/categorias", root)}
for i in range(18):
    chamar("POST", "/chamados", ana, multipart={"titulo": f"Teste de volume {i + 1}", "descricao": "<p>x</p>", "categoria_id": cat["Computador e notebook"]})
base = chamar("GET", "/chamados/parametros/painel", root)
with sync_playwright() as p:
    nav = p.chromium.launch(args=["--no-sandbox"])
    ctx = nav.new_context(viewport={"width": 1920, "height": 1080}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    pg = entrar(ctx, "joao")
    for tamanho in ("compacto", "normal", "grande"):
        chamar("PUT", "/chamados/parametros/painel", root, {**base, "tamanho": tamanho})
        pg.goto(BASE + "/chamados/painel"); pg.wait_for_selector(".painel-tv-tabela", timeout=20000)
        pg.get_by_role("button", name="Tela cheia").click(); pg.wait_for_timeout(1500)
        linhas = pg.locator(".painel-tv-tabela tbody tr").count()
        cabe = pg.evaluate("(() => { const t = document.querySelector('.painel-tv-limites'); return t.getBoundingClientRect().bottom <= window.innerHeight })()")
        pg.screenshot(path=f"/tmp/claude-1000/-home-administrador-projeto/a937eb00-77a5-42e5-a4c5-3cad418fb315/scratchpad/painel-{tamanho}.png")
        print(tamanho, "linhas na tela:", linhas, "| tudo dentro da tela:", cabe, "|", pg.inner_text(".painel-tv-paginas") if pg.locator(".painel-tv-paginas").count() else "")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    chamar("PUT", "/chamados/parametros/painel", root, base)
    nav.close()
