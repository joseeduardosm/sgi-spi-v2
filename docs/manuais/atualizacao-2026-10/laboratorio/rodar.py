import json, subprocess, sys, os
sys.path.insert(0, ".")
from cap import *
import api
ID = open("ids.txt").read().split()[0]
R = "/home/administrador/projeto/backend"
def rh(login):
    subprocess.run([f"{R}/.venv/bin/python", os.path.abspath("completar_rh.py"), login], cwd=R, env={**os.environ, "PYTHONPATH": f"{os.getcwd()}:{R}"}, capture_output=True)
def ir(pg, aba="equipe", extra=""):
    pg.goto(f"{BASE}/contratos/{ID}?aba={aba}{extra}"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1300)
def portaria_id(tok): return api.chamar("GET", f"/contratos/{ID}/portarias", tok)["portarias"][0]["id"]
def tabela(pg): return pg.locator("table.tabela-gestao").first

import functools
with sync_playwright() as p:
    nav, ctx = abrir(p)
    ctx.set_default_timeout(15000)
    # ---- Marina cria a portaria
    pg = entrar(ctx, "marina"); ir(pg); pg.wait_for_selector("#titulo-equipe", timeout=45000)
    foto(pg, "e01-equipe-nova-portaria", [(pg.locator(".cartao-pessoa-equipe").first, 1, "dir"), (pg.get_by_role("button", name="Nova portaria"), 2, "esq")],
         rolar="#titulo-equipe", legendas=["A equipe atual do contrato (só leitura nesta tela)", "Nova portaria: o único caminho para trocar gestor e fiscais"])
    try: pg.get_by_role("button", name="Nova portaria").click()
    except Exception: pg.screenshot(path="imgs/_falha.png"); raise
    pg.wait_for_selector("form.bloco-form"); pg.wait_for_timeout(500)
    def escolher(idc, texto, nome):
        campo = pg.locator(f"#nomeacao-{idc}")
        if campo.count() == 0:
            pg.locator(f"label[for=nomeacao-{idc}]").locator("xpath=..").get_by_role("button", name="Remover").click(); pg.wait_for_timeout(300)
        campo = pg.locator(f"#nomeacao-{idc}"); campo.click(); campo.fill(texto); pg.wait_for_timeout(1000)
        pg.locator("[role=option]", has_text=nome).first.click(); pg.wait_for_timeout(300)
    escolher("fiscal_tecnico", "paulo", "Paulo Andrade"); escolher("gestor_suplente", "ana", "Ana Ribeiro")
    foto(pg, "e02-nomeacoes-formulario", [(pg.locator("label[for=nomeacao-gestor]").locator("xpath=.."), 1, "esq"),
         (pg.locator("label[for=nomeacao-fiscal_tecnico]").locator("xpath=.."), 2, "dir"), (pg.get_by_role("button", name="Criar portaria"), 3, "cima")],
         rolar="form.bloco-form", legendas=["Gestor é obrigatório; o formulário já vem com a equipe atual", "Indique de 1 a 6 funções: pesquise o nome e escolha o usuário", "Criar portaria: o sistema confere o cadastro de cada nomeado no RH"])
    pg.get_by_role("button", name="Criar portaria").click(); pg.wait_for_timeout(1800)
    foto(pg, "e03-situacao-dados-pendentes", [(tabela(pg).locator("th").nth(2), 1, "cima"),
         (tabela(pg).locator("tbody tr", has_text="Ana Ribeiro").locator("td").nth(2), 2, "esq"),
         (tabela(pg).locator("tbody tr", has_text="Paulo Andrade").locator("td").nth(2), 3, "esq")],
         rolar=".portaria-cartao", legendas=["Clique no título de uma coluna para ordenar a tabela", "Dados pendentes no RH: o RH recebe o aviso para atualizar RS/PV, RG/CIN e cargo", "Cadastro completo; falta a ciência do nomeado"])
    tm = api.login("marina"); pid = portaria_id(tm)
    rh("ana")   # o RH atualiza o cadastro
    api.chamar("GET", f"/contratos/{ID}/portarias", tm)   # a consulta avança a etapa
    # ---- Paulo: aviso no sino e janela de ciência
    ctx2 = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    pp = entrar(ctx2, "paulo"); pp.wait_for_timeout(2500)
    foto(pp, "e04-janela-de-ciencia", [(pp.get_by_role("button", name="Sim, estou ciente"), 1, "cima"), (pp.get_by_role("button", name="Ainda não"), 2, "cima")],
         legendas=["Sim, estou ciente: registra a data e a hora da sua ciência", "Ainda não: fecha a janela, mas o aviso continua no sino até você dar a ciência"])
    pp.get_by_role("button", name="Ainda não").click(); pp.wait_for_timeout(500)
    pp.goto(f"{BASE}/notificacoes"); pp.wait_for_load_state("networkidle"); pp.wait_for_timeout(1200)
    foto(pp, "e05-aviso-no-sino", [(pp.locator("text=Você foi indicado como").first, 1, "esq")], legendas=["O aviso fica no sino e também chega por e-mail; abrir o aviso reabre o pedido de ciência"])
    tp, ta = api.login("paulo"), api.login("ana")
    api.chamar("POST", f"/portarias/{pid}/ciencia", tp); api.chamar("POST", f"/portarias/{pid}/ciencia", ta); api.chamar("POST", f"/portarias/{pid}/ciencia", tm)
    # ---- Marina escolhe a autoridade
    ir(pg); pg.wait_for_selector(".portaria-cartao")
    foto(pg, "e06-escolher-autoridade", [(pg.locator("select[id^=aut-]"), 1, "esq"), (pg.get_by_role("button", name="Gerar portaria e reservar número"), 2, "cima"),
         (tabela(pg).locator("tbody tr").first.locator("td").nth(2), 3, "esq")], rolar=".portaria-cartao",
         legendas=["A autoridade só é escolhida com cadastro completo e ciência de todos", "Gera o texto da portaria e reserva o número no Protocolo", "Cada nomeado com \"Dados completos\" e \"Ciência ok\" e a data e hora"])
    pg.locator("select[id^=aut-]").select_option(index=1); pg.get_by_role("button", name="Gerar portaria e reservar número").click(); pg.wait_for_timeout(2500)
    pg.set_viewport_size({"width": 1366, "height": 1180})
    foto(pg, "e07-texto-da-portaria", [(pg.locator(".aviso-reserva").first, 1, "esq"), (pg.get_by_role("button", name="Copiar o texto formatado"), 2, "esq"), (pg.locator(".texto-despacho").first, 3, "esq")],
         rolar=".aviso-reserva", legendas=["O número foi reservado e fica pendente até o Protocolo anexar o D.O.E.", "Copiar portaria: copia o texto formatado para colar no SEI", "Texto gerado a partir do modelo cadastrado em Contratos › Modelos"])
    pg.set_viewport_size({"width": 1366, "height": 860})
    # ---- Roberto aceita
    ctx3 = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    pr = entrar(ctx3, "roberto"); ir(pr); pr.wait_for_selector(".portaria-cartao", timeout=45000)
    foto(pr, "e08-aceite-da-autoridade", [(pr.get_by_role("button", name="Aceitar"), 1, "cima"), (pr.get_by_role("button", name="Devolver"), 2, "cima")], rolar=".portaria-cartao",
         legendas=["Aceitar: gera o PDF de evidência com as ciências e o seu aceite", "Devolver: informe o motivo; o número volta ao Protocolo"])
    pr.get_by_role("button", name="Aceitar").click(); pr.wait_for_timeout(600)
    pr.get_by_role("button", name="Aceitar").last.click(); pr.wait_for_timeout(2500)
    ir(pg)
    foto(pg, "e09-pdf-de-evidencia", [(pg.get_by_role("button", name="PDF de evidência (ciências e aceite)"), 1, "esq"), (pg.locator(".aviso-reserva").first, 2, "esq")], rolar=".portaria-cartao",
         legendas=["Baixe o PDF de evidência e junte ao processo no SEI", "Depois da publicação no D.O.E., o Protocolo anexa o PDF ao número reservado"])
    nav.close()
print("cenas contratos ok")
