# Criado por José Eduardo Santana Martins
# Este arquivo serve para ler o HTML dos itens como blocos (parágrafos, listas, tabelas) que a exportação Word e PDF reaproveitam.
"""HTML sanitizado do editor → blocos simples.

Um bloco é `("p", [Trecho…], alinhamento)`, `("li", [Trecho…], rótulo)` ou `("tabela", [[ [Trecho…] ]], None)`. Um `Trecho` é um texto com
os formatos ativos (negrito, itálico, sublinhado, realce, sobrescrito, subscrito) e o link, se houver.
"""

from dataclasses import dataclass

from lxml import html as lxml_html


@dataclass
class Trecho:
    texto: str
    negrito: bool = False
    italico: bool = False
    sublinhado: bool = False
    realce: bool = False
    sobrescrito: bool = False
    subscrito: bool = False
    link: str | None = None


FORMATOS = {"strong": "negrito", "b": "negrito", "em": "italico", "i": "italico", "u": "sublinhado", "mark": "realce", "sup": "sobrescrito", "sub": "subscrito"}
BLOCOS = {"p", "h1", "h2", "h3", "h4", "blockquote", "ul", "ol", "table", "div"}


def _alinhamento(no) -> str | None:
    estilo = (no.get("style") or "").replace(" ", "").lower()
    for valor in ("center", "right", "justify", "left"):
        if f"text-align:{valor}" in estilo:
            return valor
    return None


def _inline(no, formato: dict, saida: list[Trecho]) -> None:
    if no.text:
        saida.append(Trecho(no.text, **formato))
    for filho in no:
        if filho.tag == "br":
            saida.append(Trecho("\n", **formato))
        else:
            novo = dict(formato)
            if filho.tag in FORMATOS:
                novo[FORMATOS[filho.tag]] = True
            if filho.tag == "a" and filho.get("href"):
                novo["link"] = filho.get("href")
            if (filho.get("style") or "").lower().find("font-weight:bold") >= 0:
                novo["negrito"] = True
            _inline(filho, novo, saida)
        if filho.tail:
            saida.append(Trecho(filho.tail, **formato))


def trechos(no) -> list[Trecho]:
    saida: list[Trecho] = []
    _inline(no, {}, saida)
    return saida


def blocos(html: str | None) -> list[tuple]:
    """Lista de blocos do HTML (vazio se não houver conteúdo)."""
    if not html or not html.strip():
        return []
    raiz = lxml_html.fragment_fromstring(html, create_parent="div")
    resultado: list[tuple] = []
    solto: list[Trecho] = []

    def esvaziar() -> None:
        if any(t.texto.strip() for t in solto):
            resultado.append(("p", list(solto), None))
        solto.clear()

    if raiz.text and raiz.text.strip():
        solto.append(Trecho(raiz.text))
    for filho in raiz:
        if filho.tag in BLOCOS:
            esvaziar()
            resultado += _bloco(filho)
        else:
            novo = {FORMATOS[filho.tag]: True} if filho.tag in FORMATOS else {}
            if filho.tag == "br":
                solto.append(Trecho("\n"))
            else:
                _inline(filho, novo, solto)
        if filho.tail and filho.tail.strip():
            solto.append(Trecho(filho.tail))
    esvaziar()
    return resultado


def _bloco(no) -> list[tuple]:
    if no.tag in ("ul", "ol"):
        saida = []
        for n, li in enumerate([f for f in no if f.tag == "li"], start=1):
            saida.append(("li", trechos(li), f"{n}." if no.tag == "ol" else "•"))
        return saida
    if no.tag == "table":
        linhas = []
        for tr in no.iter("tr"):
            linhas.append([trechos(celula) for celula in tr if celula.tag in ("td", "th")])
        return [("tabela", linhas, None)]
    if no.tag == "div":
        return blocos(lxml_html.tostring(no, encoding="unicode", method="html").replace("<div>", "", 1).rsplit("</div>", 1)[0])
    t = trechos(no)
    if no.tag.startswith("h"):
        for x in t:
            x.negrito = True
    return [("p", t, _alinhamento(no))] if any(x.texto.strip() for x in t) else []
