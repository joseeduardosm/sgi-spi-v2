import sys, os, io
sys.path.insert(0, ".")
from cap import *
import api, fitz
from PIL import Image, ImageDraw, ImageFont, ImageChops
ID = open("ids.txt").read().split()[0]
def ir(pg, aba="equipe", extra=""):
    pg.goto(f"{BASE}/contratos/{ID}?aba={aba}{extra}"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1300)
def baixar(caminho, tok):
    import urllib.request
    r = urllib.request.Request(api.API + caminho, headers={"Authorization": f"Bearer {tok}"}); return urllib.request.urlopen(r, timeout=120).read()
def pdf_png(dados, pagina, nome, marcas=(), zoom=1.5):
    """Renderiza uma página do PDF e desenha setas numeradas ao lado dos textos encontrados: marcas = [(texto, n)]"""
    doc = fitz.open(stream=dados, filetype="pdf"); pg = doc[pagina]; pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples); d = ImageDraw.Draw(im)
    for texto, n in marcas:
        r = pg.search_for(texto)
        if not r: print("sem texto", texto); continue
        x0, y0, x1, y1 = [v * zoom for v in r[0]]
        d.rectangle([x0 - 4, y0 - 3, x1 + 4, y1 + 3], outline=(200, 35, 49), width=3)
        bx, by = max(x0 - 62, 22), (y0 + y1) / 2
        d.line([bx, by, x0 - 6, by], fill=(200, 35, 49), width=4); d.polygon([(x0 - 4, by), (x0 - 16, by - 8), (x0 - 16, by + 8)], fill=(200, 35, 49))
        d.ellipse([bx - 15, by - 15, bx + 15, by + 15], fill=(200, 35, 49)); d.text((bx, by), str(n), fill="white", anchor="mm", font=ImageFont.load_default(size=20))
    # corta o branco do fim da página (sem o rodapé), para a imagem não ficar enorme
    corpo = im.crop((0, 0, im.width, im.height - 90)); caixa = ImageChops.difference(corpo, Image.new("RGB", corpo.size, "white")).getbbox()
    if caixa and caixa[3] + 60 < im.height - 90: im = im.crop((0, 0, im.width, caixa[3] + 60))
    im.save(f"{IMG}/{nome}.png"); print("foto", nome, "páginas", len(doc))
    return len(doc)
def leg(nome, textos):
    LEG[nome] = [{"n": i + 1, "texto": t} for i, t in enumerate(textos)]; json.dump(LEG, open("legendas.json", "w"), ensure_ascii=False, indent=1)

with sync_playwright() as p:
    nav, ctx = abrir(p, 1366, 900); ctx.set_default_timeout(20000)
    # ---------- Protocolo anexa o D.O.E.
    if not os.environ.get("PULAR"):
        pp = entrar(ctx, "protocolo"); pp.goto(f"{BASE}/protocolo"); pp.wait_for_load_state("networkidle"); pp.wait_for_timeout(1500)
        pp.locator("button, [role=button]", has_text="Reservado").first.click(); pp.wait_for_timeout(1200)
        foto(pp, "p01-numero-da-portaria", [(pp.get_by_role("button", name="Anexar documento"), 1, "esq")],
             legendas=["O número da portaria aparece como Reservado, em nome do contrato. Quando o D.O.E. sair, clique em Anexar documento e envie o PDF"])
        pp.locator("input[type=file]").first.set_input_files("doe.pdf"); pp.wait_for_timeout(2500)
        foto(pp, "p02-doe-anexado", [(pp.locator("text=Utilizado").first, 1, "esq")], legendas=["Com o PDF do D.O.E. anexado, o número passa a Utilizado e a portaria é publicada no sistema: a nova equipe passa a valer"])
    # ---------- Marina: equipe publicada
    ctxm = nav.new_context(viewport={"width": 1366, "height": 900}, locale="pt-BR", timezone_id="America/Sao_Paulo"); ctxm.set_default_timeout(20000)
    pg = entrar(ctxm, "marina"); ir(pg); pg.wait_for_selector(".portaria-cartao")
    foto(pg, "e10-portaria-publicada", [(pg.locator(".cartao-pessoa-equipe", has_text="Paulo Andrade").first, 1, "dir"), (pg.locator(".portaria-cartao").first, 2, "esq")], rolar="#titulo-equipe",
         legendas=["A nova equipe passa a valer assim que o Protocolo anexa o D.O.E. (a função que a portaria não cita fica sem responsável)", "A portaria fica no histórico da própria aba Equipe, como Publicada"])
    ir(pg, "documentos"); pg.wait_for_selector("#titulo-documentos")
    foto(pg, "g01-pagamentos", [(pg.locator("#titulo-pagamentos"), 1, "esq"), (pg.locator("table").nth(1).locator("th", has_text="Documento consolidado"), 2, "cima"), (pg.locator("table").nth(1).locator("th", has_text="OB / PD"), 3, "cima")], rolar="#titulo-pagamentos",
         legendas=["Cada competência paga vira um item Pagamento MM/AAAA", "O documento consolidado da competência", "A OB/PD juntada na última etapa; a data da juntada fica na última coluna"])
    # ---------- Editar sem equipe
    pg.goto(f"{BASE}/contratos/{ID}/editar"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    foto(pg, "g02-editar-sem-equipe", [(pg.locator("#bloco-equipe"), 1, "esq")], rolar="#bloco-equipe",
         legendas=["No Editar não há mais campos de equipe: gestor e fiscais só mudam por portaria, na aba Equipe"])
    # ---------- Trilha de execução
    pg.goto(f"{BASE}/contratos/{ID}/execucao/2026-02"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1800)
    foto(pg, "g03-trilha-etapas", [(pg.locator("nav, ol").filter(has_text="CADIN").first, 1, "cima")], legendas=["O CADIN agora é a última etapa antes do download: só abre quando todas as anteriores estiverem concluídas"])
    # ---------- Diário
    ir(pg, "diario"); pg.wait_for_timeout(800)
    foto(pg, "d00-diario-baixar-pdf", [(pg.get_by_role("button", name="Baixar PDF"), 1, "esq")], legendas=["Baixar PDF: gera o diário, uma página por dia com ocorrência, com os anexos no fim"])
    nav.close()
tm = api.login("marina")
pid = api.chamar("GET", f"/contratos/{ID}/portarias", tm)["portarias"][0]["id"]
ev = baixar(f"/contratos/{ID}/portarias/{pid}/evidencia", tm)
pdf_png(ev, 0, "e11-pdf-evidencia", [("Ciência dos designados", 1), ("Aceite da autoridade competente", 2), ("Este documento deverá ser juntado", 3)])
leg("e11-pdf-evidencia", ["Data e hora da ciência de cada nomeado", "Aceite da autoridade competente, com data e hora", "Orientação para juntar o PDF ao processo no SEI"])
di = baixar(f"/contratos/{ID}/diario/pdf", tm)
n = pdf_png(di, 0, "d01-diario-pagina-do-dia", [("Terça-feira, 10 de fevereiro de 2026", 1), ("Ocorrência 1", 2)])
leg("d01-diario-pagina-do-dia", ["Uma página por dia que teve ocorrência", "Todas as ocorrências do dia, com quem registrou e quando"])
doc = fitz.open(stream=di, filetype="pdf")
for i, pgn in enumerate(doc):
    if "Lista de anexos" in pgn.get_text(): pdf_png(di, i, "d02-diario-lista-de-anexos", [("Lista de anexos", 1), ("foto-posto.pdf", 2)]); leg("d02-diario-lista-de-anexos", ["Lista de anexos no fim do diário", "Cada arquivo vem logo depois, precedido de uma folha de rosto e na página indicada"]); break
print("cenas 2 ok")
