# Criado por José Eduardo Santana Martins
# Este arquivo serve para tirar os prints do manual do lado de quem pede: abrir chamado, acompanhar, responder, avaliar, "Não resolveu" e aprovar.
import sys; sys.path.insert(0, ".")
from cap import *


def ir(pg, rota, seletor, espera=700):
    pg.goto(BASE + rota); pg.wait_for_selector(seletor, timeout=20000); pg.wait_for_timeout(espera)


with sync_playwright() as p:
    nav, ctx = abrir(p)
    pg = entrar(ctx, "maria")
    # Menu e atalhos
    ir(pg, "/chamados/meus", "tbody tr")
    foto(pg, "v01-atalhos", [(pg.locator("nav[aria-label='Atalhos dos Chamados'] a").nth(0), 1, "baixo"), (pg.locator("nav[aria-label='Atalhos dos Chamados'] a").nth(1), 2, "baixo"),
                             (pg.locator("nav[aria-label='Atalhos dos Chamados'] a.acao-primaria"), 3, "baixo")],
         legendas=["Meus chamados: tudo o que você pediu (ou que foi pedido em nome do seu setor)", "Minhas aprovações: quando alguém precisa do seu \"de acordo\"",
                   "Abrir chamado: começa um pedido novo"])
    # Abrir: catálogo
    ir(pg, "/chamados", ".cartao-categoria")
    foto(pg, "a01-catalogo", [("#nc-busca", 1, "baixo"), (pg.locator(".cartao-categoria").first, 2, "esq")],
         legendas=["Busca: digite o que está acontecendo (\"impressora\", \"senha\", \"ar\") para achar a categoria", "Cada cartão é um tipo de pedido; clique no que mais se parece com o seu"])
    pg.fill("#nc-busca", "impress"); pg.wait_for_timeout(500)
    pg.locator(".cartao-categoria").first.click(); pg.wait_for_selector("#nc-titulo", timeout=10000); pg.wait_for_timeout(600)
    pg.fill("#nc-titulo", "Impressora da sala 03B04 com papel enroscado")
    pg.locator(".editor-chamado [contenteditable=true]").first.click()
    pg.keyboard.type("Desde as 9h a impressora mostra \"papel enroscado\" e não imprime nada. Já abri a tampa e não vi papel preso.")
    pg.locator(".opcoes-sim-nao button, .opcoes-sim-nao label").first.click()
    pg.wait_for_timeout(300)
    foto(pg, "a02-formulario", [(".categoria-escolhida", 1, "esq"), ("#nc-titulo", 2, "esq"), (".editor-chamado", 3, "esq"), ("#nc-local", 4, "esq"), (".opcoes-sim-nao", 5, "esq")],
         legendas=["A categoria escolhida (\"Trocar\" volta ao catálogo)", "Título curto: o que está acontecendo, em poucas palavras", "Descrição: conte os detalhes; dá para colar print da tela aqui",
                   "Onde é o problema: a sala (o SGI já sugere a sua, pelo Patrimônio; dá para buscar outra)", "Isso está impedindo você de trabalhar? \"Sim\" sobe a prioridade"], cheia=True)
    # Meus chamados
    ir(pg, "/chamados/meus", "tbody tr")
    foto(pg, "m01-meus", [(".chips-filtro", 1, "baixo"), (pg.locator("tbody tr").first.locator("td").nth(3), 2, "dir"), (pg.locator("th").filter(has_text="Aberto"), 3, "cima")],
         legendas=["Filtros: abertos, aguardando você (a equipe perguntou algo), resolvidos e todos", "Situação de cada pedido", "Clique no título da coluna para ordenar"])
    ctx.close()

    ctx = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    pg = entrar(ctx, "ana")
    ir(pg, "/chamados/2", "#titulo-andamento")
    foto(pg, "m02-conversa", [("#titulo-andamento", 1, "esq"), (pg.locator(".linha-do-tempo li").last, 2, "esq"), (".editor-chamado", 3, "esq")],
         rolar="#titulo-andamento", legendas=["Andamento: tudo o que aconteceu, em ordem", "A resposta da equipe (você também recebe aviso no sino e por e-mail)",
                                               "Escreva aqui para responder; anexos são aceitos"])
    ctx.close()

    ctx = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    pg = entrar(ctx, "maria")
    ir(pg, "/chamados/5", "#titulo-satisfacao")
    foto(pg, "m03-nota", [(".notas-satisfacao", 1, "cima")], rolar="#titulo-satisfacao",
         legendas=["Um clique dá a nota do atendimento, de Péssimo a Ótimo. Depois, se quiser, escreva um comentário"])
    alvo = pg.locator("#dc-nao-resolveu")
    foto(pg, "m04-nao-resolveu", [("#dc-nao-resolveu", 1, "esq"), (pg.get_by_role("button", name="Não resolveu"), 2, "esq")], rolar="#dc-nao-resolveu",
         legendas=["Conte o que continua sem resolver", "\"Não resolveu\" devolve o chamado para a equipe, com prazo novo"])
    ctx.close()

    ctx = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    pg = entrar(ctx, "carla")
    ir(pg, "/chamados/aprovacoes", "tbody tr")
    foto(pg, "m05-aprovacoes", [(pg.locator("a.numero-chamado").first, 1, "dir")],
         legendas=["O chamado que espera o seu \"de acordo\": clique para abrir e responder"])
    pg.locator("a.numero-chamado").first.click(); pg.wait_for_selector("#titulo-aprovacoes", timeout=20000); pg.wait_for_timeout(800)
    sec = pg.locator("section[aria-labelledby='titulo-aprovacoes']")
    foto(pg, "m06-responder-aprovacao", [(sec.locator("textarea").first, 1, "esq"), (sec.locator("button.acao-positiva").first, 2, "cima"), (sec.locator("button.acao-recusar").first, 3, "cima")],
         rolar="#titulo-aprovacoes", legendas=["Resposta (obrigatória para não aprovar)", "Aprovar: o atendimento segue", "Não aprovar: quem pediu é avisado com o seu motivo"])
    ctx.close(); nav.close()
