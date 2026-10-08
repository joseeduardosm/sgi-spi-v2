# Criado por José Eduardo Santana Martins
# Este arquivo serve para preparar o HTML das páginas do BookStack para exibir no portal (sanitização e reescrita de links e imagens).
"""Preparação do HTML do BookStack.

1. Imagens (`/uploads/...` da própria instância) perdem o `src` e ganham `data-caminho`: o navegador não manda o token ao carregar um
   `<img src>`, então o portal baixa a imagem pela API (`/api/manuais/imagem`) e a mostra depois. Imagens de outros sites são removidas.
2. Links para páginas do BookStack viram links do portal (`/manuais/paginas/<id>`); os demais abrem em nova aba.
3. Tudo passa por uma lista fechada de marcações (nh3): sem scripts, iframes, estilos nem eventos.
"""

import re
from collections.abc import Mapping
from urllib.parse import urlparse

import lxml.html
import nh3

TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s", "sub", "sup", "mark", "small", "code", "pre", "kbd", "hr", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "a", "img", "div", "span", "figure", "figcaption", "details", "summary",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col", "dl", "dt", "dd",
}
ATRIBUTOS = {
    "*": {"id", "class"},
    "a": {"href", "title", "target"},
    "img": {"data-caminho", "alt", "title", "width", "height"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
# Caminhos de imagem aceitos (nada de `..`, esquemas ou outros diretórios)
CAMINHO_IMAGEM = re.compile(r"^/uploads/[A-Za-z0-9_\-./%+ ]+$")


def caminho_imagem_valido(caminho: str) -> bool:
    """`/uploads/images/gallery/2026-01/foto.png` sim; `/uploads/../.env`, `//host/x` ou `http://...` não."""
    return bool(CAMINHO_IMAGEM.match(caminho)) and ".." not in caminho and "//" not in caminho


def preparar_html(html: str, url_base: str, mapa_paginas: Mapping[tuple[str, str], int] | None = None) -> str:
    """HTML seguro da página, com imagens e links reescritos para o portal."""
    if not (html or "").strip():
        return ""
    mapa = mapa_paginas or {}
    raiz = lxml.html.fromstring(f"<div>{html}</div>")
    # Hosts do próprio BookStack: o endereço configurado e o das imagens de `/uploads/` da página (o BookStack grava o endereço pelo qual
    # foi acessado na hora da edição, que pode ser outro, como o IP do servidor)
    hosts = {urlparse(url_base).netloc.lower()}
    for imagem in raiz.iter("img"):
        analisada = urlparse(imagem.get("src", ""))
        if analisada.netloc and analisada.path.startswith("/uploads/"):
            hosts.add(analisada.netloc.lower())

    for imagem in raiz.iter("img"):
        origem = imagem.get("src", "")
        analisada = urlparse(origem)
        # Só `/uploads/...`: o servidor baixa SEMPRE do BookStack configurado (o host da imagem nunca é acessado), então nada de SSRF
        imagem.attrib.pop("src", None)
        imagem.attrib.pop("srcset", None)
        if caminho_imagem_valido(analisada.path):
            imagem.set("data-caminho", analisada.path)
        else:
            imagem.getparent().remove(imagem) if imagem.getparent() is not None else None

    for ancora in raiz.iter("a"):
        destino = ancora.get("href", "")
        if destino.startswith("#") or not destino:
            continue
        analisado = urlparse(destino)
        if analisado.netloc and analisado.netloc.lower() not in hosts:
            ancora.set("target", "_blank")
            continue
        encontrado = re.match(r"^/link/(\d+)$", analisado.path)
        if encontrado:
            ancora.set("href", f"/manuais/paginas/{encontrado.group(1)}" + (f"#{analisado.fragment}" if analisado.fragment else ""))
            continue
        pagina = re.match(r"^/books/([^/]+)/page/([^/]+)$", analisado.path)
        if pagina and (pagina.group(1), pagina.group(2)) in mapa:
            ancora.set("href", f"/manuais/paginas/{mapa[(pagina.group(1), pagina.group(2))]}" + (f"#{analisado.fragment}" if analisado.fragment else ""))
            continue
        # Outro endereço do BookStack (ex.: estante ou capítulo): abre lá, em nova aba
        ancora.set("href", url_base.rstrip("/") + destino if destino.startswith("/") else destino)
        ancora.set("target", "_blank")

    interno = (raiz.text or "") + "".join(lxml.html.tostring(filho, encoding="unicode") for filho in raiz)
    return nh3.clean(interno, tags=TAGS, attributes=ATRIBUTOS, url_schemes={"http", "https", "mailto"}, link_rel="noopener noreferrer").strip()


def trecho_seguro(texto: str) -> str:
    """Trecho de busca: só `<strong>` (o destaque do termo) sobrevive."""
    return nh3.clean(texto or "", tags={"strong"}, attributes={}).strip()
