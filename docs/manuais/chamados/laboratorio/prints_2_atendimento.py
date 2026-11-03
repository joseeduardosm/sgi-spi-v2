# Criado por José Eduardo Santana Martins
# Este arquivo serve para tirar os prints do manual do lado de quem atende: fila, assumir, responder, resposta pronta, pendente, resolver, painel e relatórios.
import sys; sys.path.insert(0, ".")
from cap import *
from cliente import chamar, login


def ir(pg, rota, seletor, espera=800):
    pg.goto(BASE + rota); pg.wait_for_selector(seletor, timeout=20000); pg.wait_for_timeout(espera)


with sync_playwright() as p:
    nav, ctx = abrir(p)
    pg = entrar(ctx, "joao")
    ir(pg, "/chamados/fila", "tbody tr")
    linha = pg.locator("tbody tr").first
    foto(pg, "f01-fila", [(".chips-filtro", 1, "baixo"), (linha.locator("td").nth(5), 2, "esq"), (linha.locator("a").first, 3, "dir")],
         legendas=["Filtros: abertos, meus, do meu setor, novos, sem responsável, resolvidos e todos",
                   "Prazo de solução: a cor muda com o tempo gasto (amarelo 50%, laranja 75%, vermelho 90%) e sempre vem com o texto",
                   "Clique no chamado para abrir. A fila se atualiza sozinha quando chega um chamado novo"])
    ir(pg, "/chamados/1", ".coluna-chamado")
    foto(pg, "f02-assumir", [(pg.get_by_role("button", name="Assumir o chamado"), 1, "esq"), (pg.locator("aside .selo-situacao").first, 2, "esq")],
         legendas=["Assumir: o chamado passa a ser seu e o prazo de atendimento é cumprido", "Prazos de atendimento e de solução, com a cor e a porcentagem do tempo gasto"])
    pg.get_by_role("button", name="Assumir o chamado").click(); pg.wait_for_timeout(1200)
    pg.select_option("#dc-pronta", index=1); pg.wait_for_timeout(600)
    foto(pg, "f03-responder", [("#dc-pronta", 1, "esq"), (".editor-chamado", 2, "esq"), ("form.composicao-chamado label.linha-caixa", 3, "esq")], rolar="form.composicao-chamado",
         legendas=["Resposta pronta: insere um texto padrão (cadastrado nos Parâmetros), que você pode ajustar", "O texto da resposta",
                   "Mensagem privada: só a equipe que atende vê (anotações internas)"])
    pg.get_by_role("button", name="Pôr em pendente").click(); pg.wait_for_timeout(500)
    pg.select_option("#dc-motivo", index=1); pg.wait_for_timeout(300)
    foto(pg, "f04-pendente", [("#dc-motivo", 1, "esq"), ("#dc-pendente", 2, "esq")], rolar="#dc-motivo",
         legendas=["Motivo padronizado (lista dos Parâmetros)", "Ou escreva o que falta: o solicitante é avisado e o prazo de solução para de contar"])
    pg.get_by_role("button", name="Cancelar").first.click(); pg.wait_for_timeout(300)
    pg.get_by_role("tab", name="Resolver").click(); pg.wait_for_timeout(500)
    foto(pg, "f05-resolver", [(pg.get_by_role("tab", name="Resolver"), 1, "cima"), (".editor-chamado", 2, "esq")], rolar="form.composicao-chamado",
         legendas=["A aba Resolver troca a resposta pela solução", "Escreva o que foi feito: o solicitante é avisado, dá a nota e ainda pode dizer \"Não resolveu\" por alguns dias úteis"])
    # Painel de quem atende e relatórios
    # Painel com poucas linhas por página só para mostrar a navegação no print (a configuração volta ao padrão logo depois)
    root = login("root", "senha-teste")
    config = chamar("GET", "/chamados/parametros/painel", root)
    chamar("PUT", "/chamados/parametros/painel", root, {**config, "linhas_por_pagina": 3})
    ir(pg, "/chamados/painel", ".painel-tv-tabela", 1500)
    foto(pg, "p01-painel", [("h1", 1, "dir"), (".painel-tv-indicadores", 2, "baixo"), (pg.locator(".painel-tv-tabela tbody tr").first, 3, "esq"),
                            (pg.get_by_role("button", name="Próxima página"), 4, "cima"), (pg.get_by_role("button", name="Tela cheia"), 5, "baixo")],
         legendas=["O seu setor: o painel mostra os chamados em que ele é o setor responsável", "Números do momento: abertos, sem responsável, prazo estourado e resolvidos hoje",
                   "Sempre pela cor: os vermelhos primeiro, depois os laranjas, os amarelos e os brancos. Clique na linha para abrir o chamado",
                   "Troca de página na mão (ou pelas setas ← → do teclado); sozinho, ele troca a cada poucos segundos", "Tela cheia, para deixar numa TV"])
    chamar("PUT", "/chamados/parametros/painel", root, config)
    ir(pg, "/chamados/relatorios", ".indicadores-desempenho", 2500)
    foto(pg, "r01-relatorios", [("#rc-periodo", 1, "baixo"), ("#rc-setor", 2, "baixo"), (pg.locator(".indicadores-desempenho").nth(1), 3, "esq")],
         legendas=["Período: 7, 30, 90 dias, último ano ou personalizado", "Um setor (e os de baixo) ou todos os que você atende", "Prazos cumpridos e a nota média dos solicitantes"])
    ctx.close()
    nav.close()
