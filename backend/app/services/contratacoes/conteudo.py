# Criado por José Eduardo Santana Martins
# Este arquivo serve para tratar o conteúdo dos itens: sanitização do HTML, texto derivado, numeração e entrada em lote por marcadores.
"""Conteúdo dos itens de ETP e TR.

- O **HTML sanitizado** (`nh3`) é a fonte da verdade; o texto simples é sempre a projeção dele. Script, evento (`onclick`) e estilo fora da
  lista são removidos.
- **Numeração** calculada na hora (não é gravada): itens e subitens `1.1.2.`, incisos em romano `I -`, alíneas `a)`, subseção sem marcador.
- **Entrada em lote** (do app Licitações): texto colado com `#` (níveis numéricos), `@` (subseção), `**` (inciso) e `$$` (alínea) vira
  uma árvore, com prévia antes de gravar.
"""

import re
from dataclasses import dataclass, field
from html import escape

import nh3

TAGS = {"p", "br", "strong", "b", "em", "i", "u", "s", "mark", "ul", "ol", "li", "a", "span", "h1", "h2", "h3", "h4", "blockquote",
        "table", "thead", "tbody", "tfoot", "tr", "th", "td", "colgroup", "col", "sub", "sup"}
ATRIBUTOS = {"a": {"href", "title"}, "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"}, "col": {"span"}, "*": {"style"}, "mark": {"data-color"}}
ESTILOS = {"text-align", "color", "background-color", "font-family", "font-weight", "font-style", "text-decoration"}
LIMITE_CONTEUDO = 200_000


class ErroConteudo(ValueError):
    """Conteúdo inválido (vira 400)."""


def sanitizar(html: str) -> str:
    """HTML permitido do editor: formatação, listas, tabelas e links http(s)/mailto; o resto sai."""
    if len(html or "") > LIMITE_CONTEUDO:
        raise ErroConteudo("O conteúdo do item é grande demais.")
    return nh3.clean(html or "", tags=TAGS, attributes=ATRIBUTOS, url_schemes={"http", "https", "mailto"}, link_rel="noopener noreferrer",
                     filter_style_properties=ESTILOS, strip_comments=True)


def texto_do_html(html: str) -> str:
    """Projeção em texto: blocos viram linhas, `<br>` vira quebra e o resto das tags sai."""
    quebrado = re.sub(r"(?i)<br\s*/?>|</(p|li|tr|h\d|blockquote)>", "\n", html or "")
    limpo = nh3.clean(quebrado, tags=set())
    # nh3 devolve entidades (&amp;): volta ao caractere para o texto ficar legível
    limpo = limpo.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    return re.sub(r"\n{3,}", "\n\n", limpo).strip()


def html_do_texto(texto: str) -> str:
    """Texto simples → parágrafos HTML (uma linha por parágrafo)."""
    linhas = [linha.strip() for linha in (texto or "").splitlines() if linha.strip()]
    return "".join(f"<p>{escape(linha)}</p>" for linha in linhas)


def normalizar(texto: str | None, html: str | None) -> tuple[str, str | None]:
    """Devolve (conteúdo em texto, HTML sanitizado). Sem HTML, o HTML nasce do texto; com HTML, o texto é derivado dele."""
    if html and html.strip():
        limpo = sanitizar(html)
        return texto_do_html(limpo), limpo or None
    texto = (texto or "").strip()
    if len(texto) > LIMITE_CONTEUDO:
        raise ErroConteudo("O conteúdo do item é grande demais.")
    return texto, (html_do_texto(texto) or None)


# --- Numeração -----------------------------------------------------------------------------------

def _romano(n: int) -> str:
    resultado = ""
    for valor, letra in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= valor:
            resultado, n = resultado + letra, n - valor
    return resultado


def _letra(n: int) -> str:
    texto = ""
    while n > 0:
        n, resto = divmod(n - 1, 26)
        texto = chr(97 + resto) + texto
    return texto


def marcadores(secao_ordem: int, itens: list) -> dict:
    """Marcador de cada item de uma seção, por id: `{id: "1.2.1."}`, `{id: "I -"}`, `{id: "a)"}` ou `""` (subseção).

    `itens` são os itens da seção (qualquer ordem); a hierarquia vem de `pai_id`.
    """
    filhos: dict = {}
    for i in itens:
        filhos.setdefault(i.pai_id, []).append(i)
    resultado: dict = {}

    def percorrer(pai_id, prefixo: str) -> None:
        contadores = {"num": 0, "inciso": 0, "alinea": 0}
        for i in sorted(filhos.get(pai_id, []), key=lambda x: (x.ordem, str(x.id))):
            if i.tipo in ("item", "subitem"):
                contadores["num"] += 1
                caminho = f"{prefixo}.{contadores['num']}" if prefixo else f"{secao_ordem}.{contadores['num']}"
                resultado[i.id] = f"{caminho}."
                percorrer(i.id, caminho)
                continue
            if i.tipo == "inciso":
                contadores["inciso"] += 1
                resultado[i.id] = f"{_romano(contadores['inciso'])} -"
            elif i.tipo == "alinea":
                contadores["alinea"] += 1
                resultado[i.id] = f"{_letra(contadores['alinea'])})"
            else:
                resultado[i.id] = ""
            percorrer(i.id, prefixo)

    percorrer(None, "")
    return resultado


# --- Entrada em lote -----------------------------------------------------------------------------

@dataclass
class NoLote:
    tipo: str
    conteudo: str
    nivel: int
    filhos: list["NoLote"] = field(default_factory=list)


def interpretar_lote(texto: str, maximo_niveis: int = 6) -> list[NoLote]:
    """Árvore a partir de linhas marcadas: `#`..`######` (item ou subitem por nível), `@` subseção, `**` inciso, `$$` alínea.

    Linha sem marcador continua o conteúdo da anterior. Os filhos de `@`, `**` e `$$` ficam um nível abaixo do último `#`.
    """
    raiz = NoLote("raiz", "", 0)
    pilha: list[NoLote] = [raiz]
    ultimo: NoLote | None = None
    for bruta in (texto or "").splitlines():
        linha = bruta.strip()
        if not linha:
            continue
        marca = re.match(r"^(#{1,6}|@|\*\*|\$\$)\s*(.*)$", linha)
        if not marca:
            if ultimo is not None:
                ultimo.conteudo = f"{ultimo.conteudo}\n{linha}"
            continue
        simbolo, conteudo = marca.group(1), marca.group(2).strip()
        if simbolo.startswith("#"):
            nivel = len(simbolo)
            if nivel > maximo_niveis:
                raise ErroConteudo(f"Use no máximo {maximo_niveis} níveis de `#`.")
            tipo = "item" if nivel == 1 else "subitem"
        else:
            tipo = {"@": "subsecao", "**": "inciso", "$$": "alinea"}[simbolo]
            # Fica um nível abaixo do último item numérico aberto
            nivel = (pilha[-1].nivel + 1) if pilha[-1].tipo in ("item", "subitem") else pilha[-1].nivel
        while len(pilha) > 1 and pilha[-1].nivel >= nivel:
            pilha.pop()
        no = NoLote(tipo, conteudo, nivel)
        pilha[-1].filhos.append(no)
        pilha.append(no)
        ultimo = no
    return raiz.filhos


def achatar_lote(nos: list[NoLote], profundidade: int = 0) -> list[dict]:
    """Prévia plana (`[{"tipo", "conteudo", "profundidade"}]`) para a tela mostrar antes de gravar."""
    saida: list[dict] = []
    for no in nos:
        saida.append({"tipo": no.tipo, "conteudo": no.conteudo, "profundidade": profundidade})
        saida += achatar_lote(no.filhos, profundidade + 1)
    return saida
