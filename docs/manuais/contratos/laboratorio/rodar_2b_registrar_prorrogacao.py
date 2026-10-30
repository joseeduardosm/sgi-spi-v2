# Registra a prorrogação normal (o modal tem contagem regressiva) e captura o modal e o resultado.
import sys; sys.path.insert(0, "."); sys.path.append("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio")
from cap import *
ID = open("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio/ids.txt").read().split()[0]
with sync_playwright() as p:
    nav, ctx = abrir(p); ctx.set_default_timeout(20000)
    pg = entrar(ctx, "marina"); pg.goto(f"{BASE}/contratos/{ID}/prorrogacao"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2000)
    pg.fill("#ta-data", "2026-11-20"); pg.fill("#ta-numero", "1º TA – 900/2026")
    print(pg.locator("#prorrogacao-meses").input_value(), pg.locator("#ta-data").input_value())
    pg.locator("#titulo-formalizacao").locator("xpath=ancestor::section").locator("input[type=file]").first.set_input_files("/tmp/claude-1000/-home-administrador-projeto/c4951002-22de-4ee7-9c3e-233abe2322d7/scratchpad/termo.pdf"); pg.wait_for_timeout(500)
    pg.get_by_role("button", name="Registrar prorrogação").first.click(); pg.wait_for_timeout(6500)
    foto(pg, "pr04-confirmar-prorrogacao", [(pg.get_by_role("button", name="Cancelar").last, 1, "cima")], legendas=["A janela confirma a nova vigência e o que vai acontecer; o botão de confirmar libera após uma contagem curta"])
    pg.get_by_role("button", name="Registrar prorrogação").last.click(); pg.wait_for_timeout(3000)
    pg.goto(f"{BASE}/contratos/{ID}"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2500)
    foto(pg, "pr10-contrato-apos-prorrogacao", [], legendas=None)
    nav.close()
