# Prints do manual: Processo Financeiro (pedido ao DOF e preenchimento pelo Financeiro).
import sys; sys.path.insert(0, "."); sys.path.append("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio")
from cap import *
ID = open("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio/ids.txt").read().split()[0]
with sync_playwright() as p:
    nav, ctx = abrir(p); ctx.set_default_timeout(20000)
    pg = entrar(ctx, "marina")
    pg.goto(f"{BASE}/contratos/{ID}/editar"); pg.wait_for_load_state("networkidle"); pg.wait_for_selector("#processo-financeiro", timeout=30000)
    foto(pg, "pf01-campo-processo-financeiro", [(pg.locator("#processo-financeiro"), 1, "esq"), (pg.get_by_role("button", name="Pedir processo financeiro ao DOF"), 2, "cima")] ,
         rolar="#bloco-sei", legendas=["Campo Processo Financeiro: o número do processo das ordens bancárias no SIGEO (opcional)", "Pedir processo financeiro ao DOF: avisa o Financeiro por e-mail e pelo sino"] )
    pg.get_by_role("button", name="Pedir processo financeiro ao DOF").click(); pg.wait_for_timeout(800)
    foto(pg, "pf01b-confirmar-pedido", [(pg.get_by_role("button", name="Enviar pedido"), 1, "cima"), (pg.get_by_role("button", name="Cancelar").last, 2, "cima")], legendas=["Enviar pedido: o Financeiro recebe e-mail e aviso no sino", "Cancelar: fecha sem avisar ninguém"])
    pg.get_by_role("button", name="Enviar pedido").click(); pg.wait_for_timeout(2500)
    foto(pg, "pf02-pedido-feito", [(pg.get_by_text("Último pedido ao DOF"), 1, "esq")], rolar="#bloco-sei", legendas=["Depois do pedido, o sistema mostra a data, a hora e quem pediu, para ninguém pedir duas vezes sem saber"])
    # DOF
    ctx2 = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo"); ctx2.set_default_timeout(20000)
    d = entrar(ctx2, "dof"); d.wait_for_timeout(1500)
    d.goto(f"{BASE}/notificacoes"); d.wait_for_load_state("networkidle"); d.wait_for_timeout(1200)
    foto(d, "pf03-aviso-no-sino", [(d.locator("text=processo financeiro").first, 1, "esq")], legendas=["O aviso do pedido chega ao Financeiro (também por e-mail), com o link da tela do contrato"])
    d.goto(f"{BASE}/contratos/{ID}/editar"); d.wait_for_load_state("networkidle"); d.wait_for_selector("#processo-financeiro-dof", timeout=30000)
    foto(d, "pf04-tela-do-dof", [(d.locator("#processo-financeiro-dof"), 1, "esq"), (d.get_by_role("button", name="Salvar processo financeiro"), 2, "esq")],
         legendas=["O Financeiro só pode preencher este campo; o resto do contrato aparece bloqueado", "Salvar processo financeiro: grava e fecha o pedido"])
    d.fill("#processo-financeiro-dof", "20260315789"); d.get_by_role("button", name="Salvar processo financeiro").click(); d.wait_for_timeout(2500)
    pg.goto(f"{BASE}/contratos/{ID}/editar"); pg.wait_for_load_state("networkidle"); pg.wait_for_selector("#processo-financeiro", timeout=30000)
    foto(pg, "pf06-processo-preenchido", [(pg.locator("#processo-financeiro"), 1, "esq")], rolar="#bloco-sei", legendas=["Processo preenchido pelo DOF: a partir daqui o SIGEO confere as ordens bancárias deste contrato"])
    nav.close()
