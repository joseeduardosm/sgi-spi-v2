# Criado por José Eduardo Santana Martins
# Este arquivo serve para limpar o HTML das notícias (só a marcação do editor passa) e gerar slugs e textos puros.
"""Sanitização do corpo das notícias.

O editor da tela produz HTML simples. No servidor, tudo o que não está na lista abaixo é removido (scripts, estilos,
eventos, iframes), e os links ganham `rel="noopener noreferrer"`. Assim o portal público pode exibir o HTML sem risco.
"""

import re
import unicodedata

import nh3

TAGS = {"p", "br", "strong", "b", "em", "i", "u", "s", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "a", "hr",
        "table", "thead", "tbody", "tr", "th", "td"}
ATRIBUTOS = {"a": {"href", "title", "target"}}


def limpar_html(html: str) -> str:
    """HTML seguro para publicação (lista fechada de marcações; links http, https e mailto)."""
    return nh3.clean(html or "", tags=TAGS, attributes=ATRIBUTOS, url_schemes={"http", "https", "mailto"},
                     link_rel="noopener noreferrer").strip()


def texto_puro(html: str) -> str:
    """Texto sem marcação, com espaços normalizados (busca e resumo)."""
    texto = nh3.clean(re.sub(r"<(br|/p|/li|/h\d)\s*/?>", " ", html or ""), tags=set())
    return re.sub(r"\s+", " ", texto.replace("&nbsp;", " ").replace("&amp;", "&")).strip()


def texto_para_html(texto: str) -> str:
    """Texto puro (ex.: notícias migradas) em parágrafos HTML; linhas simples viram <br> e endereços viram links."""
    from html import escape
    blocos = [b.strip() for b in re.split(r"\n\s*\n", (texto or "").replace("\r\n", "\n")) if b.strip()]
    ligar = lambda t: re.sub(r"(https?://[^\s<]+[^\s<.,;:)])", r'<a href="\1" target="_blank">\1</a>', t)
    return limpar_html("".join(f"<p>{ligar(escape(b)).replace(chr(10), '<br>')}</p>" for b in blocos))


def slug_de(titulo: str) -> str:
    """Endereço amigável a partir do título ("Campanha do Agasalho 2026" → "campanha-do-agasalho-2026")."""
    base = unicodedata.normalize("NFKD", titulo or "").encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return (base or "noticia")[:200].strip("-")
