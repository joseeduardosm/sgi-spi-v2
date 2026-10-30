# Capturas das novidades da prorrogação: trilha atualizada (6 etapas), minutas, enquadramento e pós-assinatura.
import sys; sys.path.insert(0, "."); sys.path.append("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio")
from cap import *
ID = open("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio/ids.txt").read().split()[0]
PDF = "/tmp/claude-1000/-home-administrador-projeto/c4951002-22de-4ee7-9c3e-233abe2322d7/scratchpad/termo.pdf"

def ir(pg, rota):
    pg.goto(f"{BASE}/contratos/{ID}/{rota}"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2000)

with sync_playwright() as p:
    nav, ctx = abrir(p); ctx.set_default_timeout(20000)
    pg = entrar(ctx, "marina"); ir(pg, "prorrogacao")

    # ── pr01: trilha atualizada (6 etapas, 3 opcionais) ──────────────────────
    foto(pg, "pr01-pagina-prorrogacao",
         [(pg.locator("app-trilha-etapas").first, 1, "esq"),
          (pg.locator("#titulo-identificacao"), 2, "esq")],
         legendas=[
             "A trilha mostra as 6 etapas; as marcadas como Opcional não bloqueiam o Registro",
             "Identificação do objeto: confira contrato, contratada e a vigência atual",
         ])

    # Preenche o prazo para ativar as demais seções
    pg.fill("#prorrogacao-meses", "12"); pg.wait_for_timeout(500)

    # ── pr11: minutas e despachos ──────────────────────────────────────────────
    pg.wait_for_selector("app-minutas-prorrogacao", timeout=8000); pg.wait_for_timeout(500)
    foto(pg, "pr11-minutas-lista",
         [(pg.locator("app-minutas-prorrogacao"), 1, "esq")],
         rolar="app-minutas-prorrogacao",
         legendas=[
             "Minutas e despachos (opcional): lista dos 7 documentos do processo; clique em Ver texto para copiar ao SEI",
         ])

    # ── pr12: enquadramento ───────────────────────────────────────────────────
    pg.wait_for_selector("app-enquadramento-prorrogacao", timeout=8000); pg.wait_for_timeout(500)
    foto(pg, "pr12-enquadramento",
         [(pg.locator("app-enquadramento-prorrogacao"), 1, "esq")],
         rolar="app-enquadramento-prorrogacao",
         legendas=[
             "Enquadramento no Parecer Referencial NLC nº 1/2026 (opcional): 37 itens; os verificáveis pelo sistema já chegam preenchidos",
         ])

    # Preenche formalização e registra para capturar o pós-assinatura
    pg.fill("#ta-data", "2026-10-20"); pg.fill("#ta-numero", "1º TA – 900/2026")
    pg.locator("#titulo-formalizacao").locator("xpath=ancestor::section").locator("input[type=file]").first.set_input_files(PDF); pg.wait_for_timeout(500)
    pg.get_by_role("button", name="Salvar rascunho").click(); pg.wait_for_timeout(1500)
    pg.get_by_role("button", name="Registrar prorrogação").first.click(); pg.wait_for_timeout(6500)
    pg.get_by_role("button", name="Registrar prorrogação").last.click(); pg.wait_for_timeout(3000)
    ir(pg, "prorrogacao")

    # ── pr13: depois da assinatura ────────────────────────────────────────────
    pg.wait_for_selector("section[aria-labelledby^=titulo-pos-]", timeout=10000)
    pg.locator("section[aria-labelledby^=titulo-pos-]").first.scroll_into_view_if_needed(); pg.wait_for_timeout(600)
    foto(pg, "pr13-pos-assinatura",
         [(pg.locator("section[aria-labelledby^=titulo-pos-]").first, 1, "esq")],
         legendas=[
             "Depois da assinatura: informe a publicação no PNCP (condição de eficácia), no DOE e no Contratos.gov; se o contrato exigir garantia, os campos de dados para a planilha da DOF aparecem aqui",
         ])

    nav.close()
