# Prints do manual: prorrogação normal e vigência retroativa (com os dois modais de confirmação).
import sys; sys.path.insert(0, "."); sys.path.append("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio")
from cap import *
ID = open("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio/ids.txt").read().split()[0]
PDF = "/tmp/claude-1000/-home-administrador-projeto/c4951002-22de-4ee7-9c3e-233abe2322d7/scratchpad/termo.pdf"
def ir(pg, rota):
    pg.goto(f"{BASE}/contratos/{ID}/{rota}"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2000)
with sync_playwright() as p:
    nav, ctx = abrir(p); ctx.set_default_timeout(20000)
    pg = entrar(ctx, "marina"); ir(pg, "prorrogacao")
    foto(pg, "pr01-pagina-prorrogacao", [(pg.locator("app-trilha-etapas").first, 1, "esq"), (pg.locator("#titulo-identificacao"), 2, "esq")], legendas=["A trilha mostra as 5 etapas e quanto já foi feito", "Identificação do objeto: confira contrato, contratada e a vigência atual"])
    pg.fill("#prorrogacao-meses", "12"); pg.wait_for_timeout(300)
    pg.fill("#ta-data", "2026-11-20"); pg.fill("#ta-numero", "1º TA – 900/2026")
    pg.locator("input[type=file]").first.set_input_files(PDF); pg.wait_for_timeout(500)
    foto(pg, "pr02-prazo-e-formalizacao", [(pg.locator("#prorrogacao-meses"), 1, "esq"), (pg.locator("#ta-data"), 2, "esq"), (pg.locator("#ta-numero"), 3, "esq")],
         rolar="#titulo-prazo", cheia=False, legendas=["Prazo da prorrogação em meses (não passa da vigência máxima)", "Data de assinatura do Termo Aditivo", "Número do Termo Aditivo"])
    pg.get_by_role("button", name="Salvar rascunho").click(); pg.wait_for_timeout(2000)
    foto(pg, "pr03-rascunho-salvo", [(pg.get_by_role("button", name="Registrar prorrogação"), 1, "esq")], legendas=["Registrar prorrogação fica ativo quando prazo, data e termo estão preenchidos"])
    pg.get_by_role("button", name="Registrar prorrogação").click(); pg.wait_for_timeout(800)
    foto(pg, "pr04-confirmar-prorrogacao", [], legendas=None)
    for nome in ("Confirmar", "Registrar", "Sim"):
        b = pg.get_by_role("dialog").get_by_role("button", name=nome) if pg.get_by_role("dialog").count() else None
        if b and b.count(): b.first.click(); break
    pg.wait_for_timeout(2500)
    ir(pg, "prorrogacao")
    # ---- Vigência retroativa
    pg.fill("#retroativa-meses", "12"); pg.fill("#retroativa-data", "2026-11-25"); pg.fill("#retroativa-numero", "2º TA – 900/2026")
    pg.locator("#titulo-retroativas").locator("xpath=ancestor::section").locator("input[type=file]").first.set_input_files(PDF); pg.wait_for_timeout(500)
    foto(pg, "pr05-vigencia-retroativa-formulario", [(pg.locator("#retroativa-meses"), 1, "esq"), (pg.locator("#retroativa-data"), 2, "cima"), (pg.get_by_role("button", name="Cadastrar vigência retroativa"), 3, "cima")],
         rolar="#titulo-retroativas", legendas=["Quantos meses a vigência retroativa tem (ela termina no dia anterior ao início do contrato)", "Data de assinatura do Termo Aditivo que criou a vigência", "Cadastrar: abre a janela de aviso com todos os impactos"])
    pg.get_by_role("button", name="Cadastrar vigência retroativa").click(); pg.wait_for_timeout(800)
    foto(pg, "pr06-modal-impactos", [(pg.get_by_role("button", name="Cancelar").last, 1, "cima")], legendas=["O botão de confirmar só libera depois de 10 segundos de leitura"])
    pg.wait_for_timeout(10500)
    foto(pg, "pr07-modal-impactos-liberado", [(pg.get_by_role("button", name="Li e entendi os impactos"), 1, "cima")], legendas=["Li e entendi os impactos: depois de 10 s o botão fica ativo"])
    pg.get_by_role("button", name="Li e entendi os impactos").click(); pg.wait_for_timeout(800)
    foto(pg, "pr08-modal-tem-certeza", [(pg.get_by_role("button", name="Cancelar").last, 1, "cima")], legendas=["Segunda confirmação (3 segundos): Tem certeza que deseja continuar?"])
    pg.wait_for_timeout(3500)
    pg.get_by_role("button", name="Sim, cadastrar a vigência retroativa").click(); pg.wait_for_timeout(3000)
    foto(pg, "pr09-vigencia-retroativa-cadastrada", [(pg.locator("table.tabela-gestao").last, 1, "esq")], rolar="#titulo-retroativas", legendas=["A vigência retroativa aparece na lista, com o termo e a ação Desfazer (só enquanto não há medição, reajuste ou aditamento nela)"])
    nav.close()
