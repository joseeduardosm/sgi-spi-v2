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
