# Prints do manual: reajuste normal e reajuste retroativo.
import sys; sys.path.insert(0, "."); sys.path.append("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio")
from cap import *
ID = open("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio/ids.txt").read().split()[0]
PDF = "/tmp/claude-1000/-home-administrador-projeto/c4951002-22de-4ee7-9c3e-233abe2322d7/scratchpad/termo.pdf"
def ir(pg):
    pg.goto(f"{BASE}/contratos/{ID}/reajuste"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2000)
def pdf_em(pg, ancora, rotulo_botao=None):
    """Anexa o PDF ao seletor de arquivo mais próximo do texto-âncora."""
    pg.locator(f"xpath=//*[contains(normalize-space(.), '{ancora}')]/following::input[@type='file'][1]").first.set_input_files(PDF); pg.wait_for_timeout(500)
def concluir_modal(pg, espera=6500):
    pg.wait_for_timeout(espera); pg.get_by_role("button").last.click(); pg.wait_for_timeout(3500)
def fluxo(pg, prefixo, retro):
    pg.locator("#titulo-reajuste").wait_for()
    foto(pg, f"{prefixo}02-reajuste-em-elaboracao", [(pg.locator("app-trilha-etapas").first, 1, "esq"), (pg.locator("dl.resumo-reajuste"), 2, "esq"), (pg.get_by_role("button", name="Cancelar reajuste"), 3, "cima")],
         legendas=["A trilha mostra as etapas: evidência, memória de cálculo e apostilamento", "Resumo: de quando valem os novos preços, vigência reajustada e competências recalculadas", "Cancelar reajuste: descarta a elaboração sem mudar nenhum preço"])
    pdf_em(pg, "1. Evidência do índice"); pg.get_by_role("button", name="Anexar").click(); pg.wait_for_timeout(2500)
    pg.fill("#indice-todos", "5"); pg.get_by_role("button", name="Aplicar a todos").click(); pg.wait_for_timeout(500)
    pg.get_by_role("button", name="Salvar memória").click(); pg.wait_for_timeout(2500)
    foto(pg, f"{prefixo}03-memoria-de-calculo", [(pg.locator("#indice-todos"), 1, "cima"), (pg.get_by_role("button", name="Salvar memória"), 2, "cima"), (pg.locator("div.indicadores"), 3, "cima")],
         rolar="p.secao-formulario >> nth=1" if False else None, legendas=["Percentual do índice: digite uma vez e aplique a todos os itens (depois dá para ajustar item a item)", "Salvar memória: os totais só mudam depois de salvar", "Totais: base mensal e valor global antes e depois"])
    pg.get_by_role("button", name="Gerar e baixar PDF e XLSX").click(); pg.wait_for_timeout(4000)
    pdf_em(pg, "3. Apostilamento e conclusão")
    foto(pg, f"{prefixo}04-apostilamento-e-conclusao", [(pg.get_by_role("button", name="Gerar e baixar PDF e XLSX"), 1, "cima"), (pg.get_by_role("button", name=("Concluir reajuste retroativo" if retro else "Concluir e aplicar reajuste")), 2, "cima")],
         rolar="div.indicadores", legendas=["Gera a memória em PDF e XLSX (cada geração cria uma versão nova)", "Concluir: exige evidência, memória gerada e o apostilamento assinado"])
    pg.get_by_role("button", name=("Concluir reajuste retroativo" if retro else "Concluir e aplicar reajuste")).click(); pg.wait_for_timeout(800)
    foto(pg, f"{prefixo}05-confirmar-conclusao", [], legendas=None)
    concluir_modal(pg)
with sync_playwright() as p:
    nav, ctx = abrir(p); ctx.set_default_timeout(25000)
    pg = entrar(ctx, "marina"); ir(pg)
    foto(pg, "rj01-iniciar-reajuste", [(pg.locator("#reajuste-data"), 1, "esq"), (pg.locator("#reajuste-vigencia"), 2, "cima"), (pg.get_by_role("button", name="Abrir reajuste", exact=True), 3, "cima")],
         legendas=["Data a partir da qual os novos preços valem (o mês dessa data é pago proporcional aos dias de cada preço)", "Vigência que será reajustada: uma vez só por vigência", "Abrir reajuste: cria a elaboração"])
    pg.fill("#reajuste-data", "2027-01-01"); pg.select_option("#reajuste-vigencia", index=pg.locator("#reajuste-vigencia option").count() - 1)
    pg.get_by_role("button", name="Abrir reajuste", exact=True).click(); pg.wait_for_timeout(2500)
    fluxo(pg, "rj", False)
    ir(pg)
    foto(pg, "rj06-historico", [(pg.locator("#titulo-historico-reajuste"), 1, "esq")], rolar="#titulo-historico-reajuste", legendas=["Histórico: cada reajuste com memória e apostilamento para baixar"])
    foto(pg, "rr01-iniciar-reajuste-retroativo", [(pg.locator("#reajuste-vigencia-retroativa"), 1, "esq"), (pg.get_by_role("button", name="Abrir reajuste retroativo"), 2, "cima")],
         rolar="#titulo-iniciar-retroativo", legendas=["Vigência retroativa a reajustar: uma por vez, da mais recente para a mais antiga", "Abrir reajuste retroativo: os preços partem dos da vigência seguinte"])
    pg.get_by_role("button", name="Abrir reajuste retroativo").click(); pg.wait_for_timeout(2500)
    fluxo(pg, "rr", True)
    ir(pg)
    foto(pg, "rr06-historico", [], rolar="#titulo-historico-reajuste", legendas=None)
    nav.close()
