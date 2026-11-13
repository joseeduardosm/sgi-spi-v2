"""
===============================================================================
ARQUIVO: assinatura_pptx.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Ler o modelo PPTX da assinatura de e-mail, preencher os textos com os dados
da pessoa e desenhar a imagem final em alta resolução.

RESUMO TÉCNICO:
Um PPTX é um ZIP com XMLs (DrawingML). O arquivo lê o primeiro slide com
zipfile + ElementTree e monta um Modelo em memória com três tipos de
elemento: Figura (imagens desenhadas no pixel original, sem reamostrar),
Caixa (texto com tamanho, negrito, cor RGB ou do tema, fonte, espaçamento e
margens) e Retangulo (preenchido). preencher() troca os textos de exemplo ou
as fichas {{campo}}; compactar() aproxima as linhas; desenhar() usa Pillow,
com o texto em 3x e reduzido (suavização). Fontes: `recursos/assinatura/
fontes/<nome>.ttf`, se existir; senão a Bitstream Vera do reportlab.

FINALIDADE DE NEGÓCIO:
Manter o desenho oficial da assinatura do Governo dentro de um arquivo que a
TI pode trocar: para mudar o layout basta substituir o PPTX, sem alterar
código, e a imagem sai com a nitidez do arquivo original.

CONTEXTO NO SISTEMA:
Usado somente por `assinatura_email.py` (carregar, marcar_alturas,
preencher, compactar e desenhar). O modelo fica em
`app/recursos/assinatura/modelo-assinatura.pptx`.

===============================================================================
"""

import colorsys
import copy
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import reportlab
from PIL import Image, ImageDraw, ImageFont

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
# Namespaces XML do formato Office Open XML: no XML as etiquetas aparecem como
# "a:p", "p:sp" etc.; o ElementTree precisa do endereço completo do prefixo.
# EMU (English Metric Unit) é a unidade do PowerPoint: 914400 EMU = 1 polegada,
# 12700 EMU = 1 ponto tipográfico.
EMU_POR_PT = 12700
SUPER = 3  # o texto é desenhado em 3× e reduzido
FONTES_PASTA = Path(__file__).resolve().parents[1] / "recursos" / "assinatura" / "fontes"
FONTES_REPORTLAB = Path(reportlab.__file__).resolve().parent / "fonts"
TAMANHO_PADRAO_PT = 18.0
ENCOLHER_ATE = 0.8  # um texto longo pode encolher até 80% do tamanho do modelo antes de ser abreviado


class ErroModelo(Exception):
    """O PPTX não pôde ser lido ou não tem o que a assinatura precisa."""


def _etiqueta(nome: str) -> str:
    """Converte "a:p" no nome completo que o ElementTree usa ("{namespace}p")."""
    prefixo, local = nome.split(":")
    return f"{{{NS[prefixo]}}}{local}"


# --- Modelo em memória ------------------------------------------------------------------------

@dataclass
class Estilo:
    """Estilo do texto de um parágrafo (tirado da primeira "corrida" de texto)."""
    tamanho_pt: float = TAMANHO_PADRAO_PT
    negrito: bool = False
    cor: tuple[int, int, int] = (0, 0, 0)
    fonte: str = "Verdana"


@dataclass
class Paragrafo:
    """Um parágrafo de uma caixa de texto, com estilo, alinhamento e espaçamento."""
    texto: str
    estilo: Estilo
    alinhamento: str = "l"
    espaco_pt: float | None = None  # espaçamento exato entre linhas, se o modelo definir
    espaco_pct: float | None = None  # ou proporcional (1.0 = simples)
    campo: str | None = None  # campo da assinatura que este parágrafo recebe (None = texto fixo)
    espaco_original: float | None = None  # espaçamento exato do modelo (a compactação o reduz a partir dele)


@dataclass
class Caixa:
    """Caixa de texto do slide; posição e tamanho em EMU.

    `deslocamento_y` é quanto ela foi empurrada para baixo por uma caixa de
    cima que cresceu; `altura_original` é a altura antes do preenchimento.
    """
    x: float
    y: float
    cx: float
    cy: float
    paragrafos: list[Paragrafo]
    margens: tuple[float, float, float, float] = (91440, 45720, 91440, 45720)  # esquerda, topo, direita, base (EMU)
    deslocamento_y: float = 0.0
    altura_original: float = 0.0


@dataclass
class Figura:
    """Imagem do slide (fundo do Governo, divisores, redes sociais)."""
    x: float
    y: float
    cx: float
    cy: float
    imagem: Image.Image


@dataclass
class Retangulo:
    """Retângulo de cor sólida do slide."""
    x: float
    y: float
    cx: float
    cy: float
    cor: tuple[int, int, int]


@dataclass
class Modelo:
    """O slide inteiro em memória: tamanho (EMU) e elementos na ordem de desenho."""
    largura: int  # EMU
    altura: int
    elementos: list[Figura | Retangulo | Caixa] = field(default_factory=list)

    @property
    def caixas(self) -> list[Caixa]:
        """Só as caixas de texto, na ordem do slide."""
        return [e for e in self.elementos if isinstance(e, Caixa)]


# --- Leitura do PPTX --------------------------------------------------------------------------

def _cores_do_tema(zip_: zipfile.ZipFile) -> dict[str, tuple[int, int, int]]:
    """Lê as cores do tema do PPTX (dk1, lt1, accent1...) como tuplas RGB.

    Textos podem usar "cor do tema" em vez de RGB direto; este mapa permite
    traduzir. Sem tema no arquivo, devolve só branco (bg1) e preto (tx1).
    """
    cores: dict[str, tuple[int, int, int]] = {}
    nome = next((n for n in zip_.namelist() if re.fullmatch(r"ppt/theme/theme\d+\.xml", n)), None)
    if nome is None:
        return {"bg1": (255, 255, 255), "tx1": (0, 0, 0)}
    esquema = ET.fromstring(zip_.read(nome)).find(".//a:clrScheme", NS)
    if esquema is not None:
        for filho in esquema:
            nome_cor = filho.tag.split("}")[1]
            for interno in filho:
                valor = interno.get("val") or interno.get("lastClr")
                if interno.tag.endswith("sysClr"):
                    valor = interno.get("lastClr") or valor
                if valor and re.fullmatch(r"[0-9A-Fa-f]{6}", valor):
                    cores[nome_cor] = tuple(int(valor[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[assignment]
    # O mapa de cores do slide mestre liga bg1/tx1 a lt1/dk1 (padrão do PowerPoint)
    cores.setdefault("lt1", (255, 255, 255))
    cores.setdefault("dk1", (0, 0, 0))
    cores["bg1"], cores["tx1"] = cores["lt1"], cores["dk1"]
    cores["bg2"], cores["tx2"] = cores.get("lt2", (238, 238, 238)), cores.get("dk2", (68, 68, 68))
    return cores


def _cor(elemento: ET.Element | None, tema: dict[str, tuple[int, int, int]], padrao: tuple[int, int, int]) -> tuple[int, int, int]:
    """Cor de um `a:solidFill` (RGB direto ou do tema, com `lumMod`/`lumOff`)."""
    if elemento is None:
        return padrao
    preenchimento = elemento.find("a:solidFill", NS)
    if preenchimento is None:
        return padrao
    # A cor pode vir em RGB direto (srgbClr) ou como referência ao tema (schemeClr)
    srgb = preenchimento.find("a:srgbClr", NS)
    if srgb is not None:
        base = tuple(int(srgb.get("val", "000000")[i:i + 2], 16) for i in (0, 2, 4))
        no_tema = srgb
    else:
        esquema = preenchimento.find("a:schemeClr", NS)
        if esquema is None:
            return padrao
        base = tema.get(esquema.get("val", "tx1"), padrao)
        no_tema = esquema
    modulo = no_tema.find("a:lumMod", NS)
    deslocamento = no_tema.find("a:lumOff", NS)
    if modulo is None and deslocamento is None:
        return base  # type: ignore[return-value]
    # lumMod/lumOff clareiam ou escurecem a cor base: o PowerPoint multiplica a
    # luminosidade por lumMod e soma lumOff (valores em milésimos de porcento).
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in base))
    l = l * (int(modulo.get("val", "100000")) / 100000 if modulo is not None else 1) + (int(deslocamento.get("val", "0")) / 100000 if deslocamento is not None else 0)
    return tuple(round(c * 255) for c in colorsys.hls_to_rgb(h, min(max(l, 0), 1), s))  # type: ignore[return-value]


def _estilo(rpr: ET.Element | None, tema: dict[str, tuple[int, int, int]]) -> Estilo:
    """Monta o Estilo a partir de um `a:rPr` (propriedades da corrida de texto).

    O tamanho `sz` vem em centésimos de ponto (1800 = 18 pt).
    """
    if rpr is None:
        return Estilo()
    latin = rpr.find("a:latin", NS)
    return Estilo(
        tamanho_pt=int(rpr.get("sz")) / 100 if rpr.get("sz") else TAMANHO_PADRAO_PT,
        negrito=rpr.get("b") == "1",
        cor=_cor(rpr, tema, (0, 0, 0)),
        fonte=latin.get("typeface", "Verdana") if latin is not None else "Verdana",
    )


def _xfrm(forma: ET.Element) -> tuple[float, float, float, float]:
    """Posição (x, y) e tamanho (cx, cy) da forma, em EMU; erro se não houver."""
    xfrm = forma.find(".//a:xfrm", NS)
    if xfrm is None:
        raise ErroModelo("Uma forma do modelo não tem posição.")
    deslocamento, extensao = xfrm.find("a:off", NS), xfrm.find("a:ext", NS)
    return float(deslocamento.get("x")), float(deslocamento.get("y")), float(extensao.get("cx")), float(extensao.get("cy"))  # type: ignore[union-attr]


def _paragrafos(corpo: ET.Element, tema: dict[str, tuple[int, int, int]]) -> list[Paragrafo]:
    """Converte os `a:p` de uma caixa em objetos Paragrafo.

    O texto é a soma das corridas (`a:r`); o estilo vem da primeira corrida
    (ou do `endParaRPr` num parágrafo vazio). O espaçamento pode ser exato
    (spcPts, centésimos de ponto) ou proporcional (spcPct, 100000 = simples).
    """
    resultado = []
    for p in corpo.findall("a:p", NS):
        corridas = p.findall("a:r", NS)
        texto = "".join((r.findtext("a:t", default="", namespaces=NS)) for r in corridas)
        primeira = corridas[0].find("a:rPr", NS) if corridas else p.find("a:endParaRPr", NS)
        ppr = p.find("a:pPr", NS)
        espaco_pt = espaco_pct = None
        if ppr is not None and (ln := ppr.find("a:lnSpc", NS)) is not None:
            if (pts := ln.find("a:spcPts", NS)) is not None:
                espaco_pt = int(pts.get("val")) / 100
            elif (pct := ln.find("a:spcPct", NS)) is not None:
                espaco_pct = int(pct.get("val")) / 100000
        resultado.append(Paragrafo(texto=texto, estilo=_estilo(primeira, tema), alinhamento=(ppr.get("algn", "l") if ppr is not None else "l"),
                                   espaco_pt=espaco_pt, espaco_pct=espaco_pct, espaco_original=espaco_pt))
    return resultado


@lru_cache(maxsize=4)
def _carregar_cache(caminho: str, modificado: float) -> Modelo:
    """Versão com cache de _carregar.

    `lru_cache` guarda o resultado por argumentos; como a data de modificação
    faz parte da chave, trocar o arquivo gera uma nova leitura.
    """
    return _carregar(Path(caminho))


def carregar(caminho: Path) -> Modelo:
    """Lê o PPTX (com cache por data de modificação: trocar o arquivo vale na próxima geração). Devolve uma cópia editável."""
    if not caminho.exists():
        raise ErroModelo(f"Modelo de assinatura não encontrado: {caminho.name}.")
    # deepcopy: o chamador altera o modelo (preencher/compactar); sem a cópia,
    # a alteração estragaria o objeto guardado no cache.
    return copy.deepcopy(_carregar_cache(str(caminho), caminho.stat().st_mtime))


def _carregar(caminho: Path) -> Modelo:
    """Abre o PPTX e monta o Modelo do primeiro slide.

    Passos: tamanho do slide (presentation.xml), descobre o arquivo do
    primeiro slide pelas relações (.rels), lê as cores do tema e percorre as
    formas: `p:pic` vira Figura, `p:sp` com texto vira Caixa e `p:sp` só com
    preenchimento vira Retangulo. Qualquer falha de leitura vira ErroModelo.
    """
    try:
        zip_ = zipfile.ZipFile(caminho)
        apresentacao = ET.fromstring(zip_.read("ppt/presentation.xml"))
        tamanho = apresentacao.find("p:sldSz", NS)
        largura, altura = int(tamanho.get("cx")), int(tamanho.get("cy"))  # type: ignore[union-attr]
        relacoes = {r.get("Id"): r.get("Target") for r in ET.fromstring(zip_.read("ppt/_rels/presentation.xml.rels"))}
        primeiro = apresentacao.find("p:sldIdLst/p:sldId", NS)
        alvo = relacoes[primeiro.get(_etiqueta("r:id"))]  # type: ignore[union-attr]
        slide_caminho = "ppt/" + alvo.lstrip("/").removeprefix("ppt/")
        slide = ET.fromstring(zip_.read(slide_caminho))
        rels_slide = {r.get("Id"): r.get("Target") for r in ET.fromstring(zip_.read(slide_caminho.replace("slides/", "slides/_rels/") + ".rels"))}
        tema = _cores_do_tema(zip_)
        modelo = Modelo(largura=largura, altura=altura)
        for forma in slide.find("p:cSld/p:spTree", NS):  # type: ignore[union-attr]
            if forma.tag == _etiqueta("p:pic"):
                x, y, cx, cy = _xfrm(forma)
                alvo_img = rels_slide[forma.find(".//a:blip", NS).get(_etiqueta("r:embed"))]  # type: ignore[union-attr]
                nome_img = "ppt/" + re.sub(r"^(\.\./)+", "", alvo_img)
                imagem = Image.open(io.BytesIO(zip_.read(nome_img))).convert("RGBA")
                modelo.elementos.append(Figura(x, y, cx, cy, imagem))
            elif forma.tag == _etiqueta("p:sp"):
                x, y, cx, cy = _xfrm(forma)
                sp_pr = forma.find("p:spPr", NS)
                corpo = forma.find("p:txBody", NS)
                if corpo is not None and any(t.text for t in corpo.iter(_etiqueta("a:t"))):
                    body = corpo.find("a:bodyPr", NS)
                    margens = tuple(float(body.get(k, d)) for k, d in (("lIns", 91440), ("tIns", 45720), ("rIns", 91440), ("bIns", 45720))) if body is not None else (91440, 45720, 91440, 45720)
                    modelo.elementos.append(Caixa(x, y, cx, cy, _paragrafos(corpo, tema), margens))  # type: ignore[arg-type]
                elif sp_pr is not None and sp_pr.find("a:solidFill", NS) is not None:
                    modelo.elementos.append(Retangulo(x, y, cx, cy, _cor(sp_pr, tema, (0, 0, 0))))
        if not modelo.elementos:
            raise ErroModelo("O modelo não tem imagem nem texto no primeiro slide.")
        return modelo
    except ErroModelo:
        raise
    except (KeyError, ValueError, ET.ParseError, zipfile.BadZipFile, AttributeError, OSError) as erro:
        raise ErroModelo(f"Não foi possível ler o modelo de assinatura (PPTX): {erro}") from erro


# --- Fontes e medidas --------------------------------------------------------------------------

@lru_cache(maxsize=128)
def _fonte(nome: str, negrito: bool, pixels: int) -> ImageFont.FreeTypeFont:
    """Fonte TrueType no tamanho em pixels pedido (com cache).

    Procura em `recursos/assinatura/fontes` algumas grafias comuns do arquivo
    (ex.: Verdana-Bold.ttf, verdanab.ttf); sem nenhuma, usa a Vera do reportlab.
    """
    base = re.sub(r"[^A-Za-z0-9]", "", nome)
    candidatos = [f"{base}-Bold.ttf", f"{base}Bold.ttf", f"{base.lower()}bd.ttf", f"{base.lower()}b.ttf"] if negrito else [f"{base}.ttf", f"{base.lower()}.ttf"]
    for arquivo in candidatos:
        if (FONTES_PASTA / arquivo).exists():
            return ImageFont.truetype(str(FONTES_PASTA / arquivo), size=pixels)
    return ImageFont.truetype(str(FONTES_REPORTLAB / ("VeraBd.ttf" if negrito else "Vera.ttf")), size=pixels)


def _px(emu: float, k: float) -> float:
    """Converte EMU em pixels usando a escala `k` (pixels por EMU)."""
    return emu * k


def _largura(texto: str, fonte: ImageFont.FreeTypeFont) -> float:
    """Largura do texto em pixels, na fonte dada."""
    return fonte.getlength(texto)


def _quebrar(texto: str, fonte: ImageFont.FreeTypeFont, largura: float) -> list[str]:
    """Quebra o texto em linhas que caibam em `largura` pixels, palavra por palavra.

    Uma palavra sozinha maior que a largura fica numa linha só (não é cortada).
    """
    linhas, atual = [], ""
    for palavra in texto.split():
        tentativa = f"{atual} {palavra}".strip()
        if _largura(tentativa, fonte) <= largura or not atual:
            atual = tentativa
        else:
            linhas.append(atual)
            atual = palavra
    return linhas + [atual] if atual else linhas or [""]


def _abreviar(texto: str, fonte: ImageFont.FreeTypeFont, largura: float) -> str:
    """Corta o texto letra a letra até caber com "…" no fim."""
    cortado = texto
    while cortado and _largura(cortado + "…", fonte) > largura:
        cortado = cortado[:-1]
    return cortado.rstrip() + "…"


def _passo_pt(p: Paragrafo, tamanho_pt: float) -> float:
    """Distância entre linhas do parágrafo, em pontos.

    Espaçamento exato do modelo, se houver; senão 1,2 x o tamanho da fonte
    (o "simples" do PowerPoint) vezes o fator proporcional.
    """
    if p.espaco_pt is not None:
        return p.espaco_pt
    return tamanho_pt * 1.2 * (p.espaco_pct or 1.0)


def _linhas_do_paragrafo(p: Paragrafo, largura_px: float, k: float, avisos: list[str], rotulo: str) -> tuple[ImageFont.FreeTypeFont, float, list[str]]:
    """Fonte (em pixels), tamanho em pontos e linhas do parágrafo. Campo preenchido: uma linha, encolhendo e por fim abreviando."""
    tamanho = p.estilo.tamanho_pt
    # Converte pontos em pixels na escala atual (mínimo 1 px)
    pixels = lambda pt: max(1, round(pt * EMU_POR_PT * k))  # noqa: E731
    fonte = _fonte(p.estilo.fonte, p.estilo.negrito, pixels(tamanho))
    # Texto fixo do modelo pode quebrar em várias linhas como no PowerPoint
    if p.campo is None:
        return fonte, tamanho, _quebrar(p.texto, fonte, largura_px)
    # Campo preenchido fica numa linha: reduz a fonte de 0,25 em 0,25 pt até
    # caber ou até o limite ENCOLHER_ATE (80%); se ainda não couber, abrevia.
    while _largura(p.texto, fonte) > largura_px and tamanho > p.estilo.tamanho_pt * ENCOLHER_ATE:
        tamanho -= 0.25
        fonte = _fonte(p.estilo.fonte, p.estilo.negrito, pixels(tamanho))
    if _largura(p.texto, fonte) > largura_px:
        avisos.append(f"{rotulo} muito longo: abreviado na imagem.")
        return fonte, tamanho, [_abreviar(p.texto, fonte, largura_px)]
    return fonte, tamanho, [p.texto]


# --- Preenchimento ----------------------------------------------------------------------------

def _normalizar(texto: str) -> str:
    """Minúsculas e espaços simples, para comparar com os textos de exemplo."""
    return " ".join(texto.casefold().split())


# Textos de exemplo do modelo oficial e o campo que cada um recebe
EXEMPLOS = {
    "nome sobrenome": "nome",
    "cargo": "cargo",
    "órgão ou secretaria": "orgao",
    "email@sp.gov.br | 11 0000-0000": "contato",
    "av. morumbi, 4.500 - são paulo - sp": "endereco",
}
# Nome amigável de cada campo, usado nos avisos ("Cargo muito longo...")
ROTULOS = {"nome": "Nome", "cargo": "Cargo", "orgao": "Órgão", "contato": "E-mail e telefone", "endereco": "Endereço"}
# Ficha no texto do modelo, no formato {{nome_do_campo}}
FICHA = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def preencher(modelo: Modelo, campos: dict[str, str], extras: list[str]) -> None:
    """Troca os textos de exemplo (ou as fichas `{{campo}}`) pelos dados.

    `campos`: nome, cargo, orgao, contato, endereco (e qualquer outro usado em fichas). `extras`: linhas a acrescentar abaixo
    do endereço (celular, andar/lado). Parágrafo de ficha cujos campos estão todos vazios é removido.
    """
    # Monta uma lista nova de parágrafos por caixa, pois um parágrafo de
    # exemplo pode virar vários (ou nenhum, se o campo vier vazio).
    for caixa in modelo.caixas:
        novos: list[Paragrafo] = []
        for p in caixa.paragrafos:
            chave = EXEMPLOS.get(_normalizar(p.texto))
            if chave is not None:
                # Campo com várias linhas ("a\nb"): cada linha vira um parágrafo igual ao do modelo
                linhas = [t.strip() for t in campos.get(chave, "").split("\n") if t.strip()]
                if not linhas:
                    continue  # campo sem valor: a linha some
                for texto in linhas:
                    paragrafo = copy.deepcopy(p)
                    paragrafo.texto, paragrafo.campo = texto, chave
                    novos.append(paragrafo)
                p = novos[-1]
                # As linhas extras (celular, andar/lado) entram logo abaixo do
                # endereço, copiando o estilo da última linha dele.
                if chave == "endereco":
                    for extra in extras:
                        clone = copy.deepcopy(p)
                        clone.texto, clone.campo = extra, "extra"
                        novos.append(clone)
            elif FICHA.search(p.texto):
                usados = FICHA.findall(p.texto)
                p.texto = FICHA.sub(lambda m: campos.get(m.group(1), ""), p.texto).strip()
                p.campo = usados[0] if usados else None
                if p.texto:
                    novos.append(p)
            else:
                novos.append(p)
        caixa.paragrafos = novos


# --- Desenho ----------------------------------------------------------------------------------

def _escala(modelo: Modelo) -> float:
    """Pixels por EMU: a maior resolução entre as figuras (nenhuma é reduzida), para a imagem sair no pixel original.

    Sem figuras, usa 3 x 96 dpi (288 pixels por polegada de 914400 EMU).
    """
    razoes = [f.imagem.width / f.cx for f in modelo.elementos if isinstance(f, Figura) and f.cx]
    return max(razoes) if razoes else 3 * 96 / 914400


def _altura_caixa(caixa: Caixa, k: float, largura_px: float, avisos: list[str]) -> float:
    """Altura (EMU) que a caixa ocupa com o texto atual (margens + linhas)."""
    total = caixa.margens[1] + caixa.margens[3]
    for p in caixa.paragrafos:
        _, tamanho, linhas = _linhas_do_paragrafo(p, largura_px, k, [], "")
        total += len(linhas) * _passo_pt(p, tamanho) * EMU_POR_PT
    return total


def empurrar(modelo: Modelo, k: float) -> None:
    """Caixas que cresceram (mais linhas que no modelo) empurram para baixo as que estão abaixo delas."""
    # Zera os deslocamentos para recalcular do zero a cada chamada
    for caixa in modelo.caixas:
        caixa.deslocamento_y = 0.0
    for caixa in modelo.caixas:
        largura_px = (caixa.cx - caixa.margens[0] - caixa.margens[2]) * k
        crescimento = _altura_caixa(caixa, k, largura_px, []) - caixa.altura_original
        # Empurra só as caixas que começam abaixo do meio desta e que se
        # sobrepõem a ela na horizontal (estão "embaixo" de verdade).
        if crescimento > 1:
            for outra in modelo.caixas:
                if outra is not caixa and outra.y >= caixa.y + caixa.altura_original * 0.5 and outra.x < caixa.x + caixa.cx and caixa.x < outra.x + outra.cx:
                    outra.deslocamento_y += crescimento


def fim_do_texto(modelo: Modelo) -> float:
    """Posição vertical (EMU) do fim do último texto, já com as caixas empurradas."""
    k = _escala(modelo)
    empurrar(modelo, k)
    fim = 0.0
    for caixa in modelo.caixas:
        largura_px = (caixa.cx - caixa.margens[0] - caixa.margens[2]) * k
        fim = max(fim, caixa.y + caixa.deslocamento_y + _altura_caixa(caixa, k, largura_px, []) - caixa.margens[3])
    return fim


def compactar(modelo: Modelo, limite: float) -> bool:
    """Aproxima as linhas (até 1,2× o tamanho da fonte) até o texto terminar antes de `limite` (EMU). Devolve se coube.

    Tenta fatores decrescentes sobre o espaçamento original; o último (0.0)
    equivale a usar o mínimo de 1,2 x a fonte. Altera o modelo recebido.
    """
    for fator in (1.0, 0.96, 0.92, 0.88, 0.84, 0.8, 0.0):
        for caixa in modelo.caixas:
            for p in caixa.paragrafos:
                if p.espaco_original is not None:
                    p.espaco_pt = max(p.estilo.tamanho_pt * 1.2, p.espaco_original * fator)
        if fim_do_texto(modelo) <= limite:
            return True
    return False


def desenhar(modelo: Modelo, avisos: list[str], originais: dict[int, float] | None = None, fator: float = 1.0) -> Image.Image:
    """Imagem RGB do slide. `originais`: altura (EMU) de cada caixa no modelo, para empurrar para baixo as que ficam abaixo de uma que cresceu."""
    k = _escala(modelo) * fator
    # A tela final recebe figuras e retângulos direto; o texto vai para uma
    # camada transparente SUPER vezes maior, reduzida no fim (antisserrilhado).
    largura, altura = round(modelo.largura * k), round(modelo.altura * k)
    tela = Image.new("RGBA", (largura, altura), (255, 255, 255, 255))

    empurrar(modelo, k)

    camada = Image.new("RGBA", (largura * SUPER, altura * SUPER), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(camada)
    for elemento in modelo.elementos:
        if isinstance(elemento, Figura):
            tamanho = (round(elemento.cx * k), round(elemento.cy * k))
            imagem = elemento.imagem if elemento.imagem.size == tamanho else elemento.imagem.resize(tamanho, Image.Resampling.LANCZOS)
            tela.alpha_composite(imagem, (round(elemento.x * k), round(elemento.y * k)))
        elif isinstance(elemento, Retangulo):
            ImageDraw.Draw(tela).rectangle((elemento.x * k, elemento.y * k, (elemento.x + elemento.cx) * k - 1, (elemento.y + elemento.cy) * k - 1), fill=elemento.cor + (255,))
        else:
            topo = (elemento.y + elemento.deslocamento_y + elemento.margens[1]) * k
            esquerda = (elemento.x + elemento.margens[0]) * k
            largura_px = (elemento.cx - elemento.margens[0] - elemento.margens[2]) * k
            for p in elemento.paragrafos:
                fonte_1x, tamanho, linhas = _linhas_do_paragrafo(p, largura_px, k, avisos, ROTULOS.get(p.campo or "", "Texto"))
                fonte = _fonte(p.estilo.fonte, p.estilo.negrito, max(1, round(tamanho * EMU_POR_PT * k * SUPER)))
                passo = _passo_pt(p, tamanho) * EMU_POR_PT * k
                descida = fonte_1x.getmetrics()[1]
                for linha in linhas:
                    # A linha de base fica a `descida` acima do fim da linha (como o PowerPoint com espaçamento exato)
                    base = topo + passo - descida
                    x = esquerda
                    if p.alinhamento == "ctr":
                        x += (largura_px - _largura(linha, fonte_1x)) / 2
                    elif p.alinhamento == "r":
                        x += largura_px - _largura(linha, fonte_1x)
                    desenho.text((x * SUPER, base * SUPER), linha, font=fonte, fill=p.estilo.cor + (255,), anchor="ls")
                    topo += passo
    reduzida = camada.convert("RGBa").resize((largura, altura), Image.Resampling.LANCZOS).convert("RGBA")
    tela.alpha_composite(reduzida)
    return tela.convert("RGB")


def marcar_alturas(modelo: Modelo) -> None:
    """Guarda a altura que cada caixa tem no modelo (antes de preencher) para detectar o crescimento depois.

    Deve ser chamada logo depois de carregar(), antes de preencher().
    """
    k = _escala(modelo)
    for caixa in modelo.caixas:
        caixa.altura_original = _altura_caixa(caixa, k, (caixa.cx - caixa.margens[0] - caixa.margens[2]) * k, [])
