import sys, os
sys.path.insert(0, ".")
from cap import *
import api
LISTA = open("lista.txt").read().strip()
with sync_playwright() as p:
    nav, ctx = abrir(p, 1366, 900); ctx.set_default_timeout(20000)
    pg = entrar(ctx, "fernanda")
    if os.environ.get("PARTE2"):
        pg.goto(f"{BASE}/patrimonio/inserviveis/{LISTA}"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1800)
    else:
        pg.goto(f"{BASE}/patrimonio/inserviveis"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
        foto(pg, "i01-listas-de-inserviveis", [(pg.locator("a, article, .cartao-lista, [class*=lista]").filter(has_text="Rascunho").first, 1, "esq")],
             legendas=["Cada cartão é uma lista, com o status (Rascunho, Pendente, Aprovada…) e quantos bens tem"])
        pg.goto(f"{BASE}/patrimonio/inserviveis/{LISTA}"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1800)
        foto(pg, "i02-lista-selecao", [(pg.get_by_role("button", name="Compartilhar"), 1, "cima"), (pg.locator(".pat-selecionar-todos"), 2, "esq"), (pg.locator(".pat-busca-lista"), 3, "cima"),
             (pg.get_by_role("button", name="Criar justificativa"), 4, "cima")], rolar=".pat-selecionar-todos",
             legendas=["Compartilhar: inclui colaboradores com os mesmos poderes de quem montou a lista", "Selecionar todos os bens da lista", "Pesquisa dentro da lista: chapa, série, descrição, marca, modelo, sala…", "Criar justificativa para todos os bens marcados"])
        pg.locator(".pat-selecionar-todos input").check(); pg.wait_for_timeout(300)
        pg.get_by_role("button", name="Criar justificativa").click(); pg.wait_for_timeout(1500)
        foto(pg, "i03-justificativa-categoria", [(pg.locator(".pat-categoria").first, 1, "esq"), (pg.locator("app-editor-rico").first, 2, "esq"), (pg.get_by_role("button", name="Aplicar").first, 3, "cima")],
             legendas=["Categoria do inservível (obrigatória): Ocioso, Recuperável, Antieconômico ou Irrecuperável", "Justificativa em texto formatado, de 10 a 2000 caracteres", "Aplica a categoria e a justificativa a todos os bens marcados"])
        pg.locator(".pat-categoria", has_text="Antieconômico").click()
        ed = pg.locator("app-editor-rico [contenteditable=true]").first; ed.click(); ed.type("Equipamentos com mais de 10 anos de uso, sem peças de reposição; o conserto custaria mais de 60% do valor de um novo.")
        pg.wait_for_timeout(400); pg.get_by_role("button", name="Aplicar").first.click(); pg.wait_for_timeout(1800)
    pg.get_by_role("button", name="Compartilhar").click(); pg.wait_for_timeout(1000)
    campo = pg.locator("#compartilhar-usuarios"); campo.click(); campo.fill("tereza") if not pg.locator(".ficha", has_text="Tereza").count() else None; pg.wait_for_timeout(1000); (pg.locator("[role=option]", has_text="Tereza").first.click() if pg.locator("[role=option]", has_text="Tereza").count() else None); pg.locator("#titulo-compartilhar-lista").click(); pg.wait_for_timeout(400)
    foto(pg, "i04-compartilhar-lista", [(pg.locator("#compartilhar-usuarios"), 1, "esq"), (pg.locator(".modal-portal").get_by_role("button", name="Salvar"), 2, "cima")],
         legendas=["Pesquise e escolha as pessoas que vão colaborar na lista", "Salvar: os colaboradores passam a ver e editar a lista e são avisados"])
    pg.locator(".modal-portal").get_by_role("button", name="Salvar").click(); pg.wait_for_timeout(1500)
    foto(pg, "i05-lista-justificada", [(pg.get_by_role("button", name="Editar justificativa").first, 1, "esq"), (pg.get_by_role("button", name="Enviar para aprovação"), 2, "cima")], rolar="text=Editar justificativa",
         legendas=["A justificativa já dada pode ser editada ou excluída enquanto a lista é rascunho", "Com todos os bens justificados, envie para aprovação"])
    pg.get_by_role("button", name="Enviar para aprovação").click(); pg.wait_for_timeout(1500)
    ctx2 = nav.new_context(viewport={"width": 1366, "height": 900}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    pr = entrar(ctx2, "ricardo"); pr.goto(f"{BASE}/patrimonio/inserviveis/{LISTA}"); pr.wait_for_load_state("networkidle"); pr.wait_for_timeout(1800)
    pr.get_by_role("button", name="Aprovar").first.click() if pr.get_by_role("button", name="Aprovar").count() else None
    pr.wait_for_timeout(500); pr.screenshot(path="imgs/_apr.png")
    nav.close()
print("pat ok")
