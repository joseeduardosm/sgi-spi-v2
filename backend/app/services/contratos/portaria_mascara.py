# Criado por José Eduardo Santana Martins
# Este arquivo serve para validar e preencher a máscara (modelo) da portaria com os placeholders permitidos.
"""Máscara da portaria: HTML do editor rico com placeholders `#nome` de uma **lista fechada**.

- **Validar:** qualquer `#` que não seja um placeholder da lista (inclusive `#` solto ou `#015#`) barra o salvamento. A máscara "sem
  portaria anterior" não pode usar os placeholders da portaria anterior.
- **Preencher:** troca cada placeholder pelo valor (sempre escapado). Parágrafo com placeholder de pessoa (nome ou RS) vazio é omitido, e
  os parágrafos que começam com numeração romana ("I –", "II –") são renumerados em sequência.
"""

import re
from html import escape

from lxml import html as lxml_html

VARIANTES = ("com_anterior", "sem_anterior")

# Placeholder → o que é (mostrado na tela de modelos)
PLACEHOLDERS: dict[str, str] = {
    "numeroportaria": "Número da portaria reservado no Protocolo (3 dígitos, ex.: 015)",
    "anoportaria": "Ano da portaria (ex.: 2026)",
    "numerodocontrato": "Número do contrato",
    "contratada": "Razão social da empresa contratada",
    "cnpjcontratada": "CNPJ da contratada",
    "objetodocontrato": "Objeto do contrato",
    "nroprocessosei": "Número do processo SEI de gestão do contrato",
    "nomeautoridade": "Nome da autoridade signatária",
    "nomegestor": "Nome do gestor", "rsgestor": "RS do gestor",
    "nomegestorsuplente": "Nome do gestor suplente", "rsgestorsuplente": "RS do gestor suplente",
    "nomefiscal": "Nome do fiscal (o técnico; na falta dele, o administrativo)", "rsfiscal": "RS do fiscal",
    "nomefiscaladministrativo": "Nome do fiscal administrativo", "rsfiscaladministrativo": "RS do fiscal administrativo",
    "nomefiscaladministrativosuplente": "Nome do fiscal administrativo suplente", "rsfiscaladministrativosuplente": "RS do fiscal administrativo suplente",
    "nomefiscaltecnico": "Nome do fiscal técnico", "rsfiscaltecnico": "RS do fiscal técnico",
    "nomefiscaltecnicosuplente": "Nome do fiscal técnico suplente", "rsfiscaltecnicosuplente": "RS do fiscal técnico suplente",
    "nomedocumento": "Sigla da portaria anterior (ex.: SPI SSGC, para \"Portaria #nomedocumento\")",
    "numeroportariaanterior": "Número da portaria anterior",
    "diaportariaanterior": "Dia da portaria anterior", "mesportariaanterior": "Mês da portaria anterior, por extenso", "anoportariaanterior": "Ano da portaria anterior",
}
DA_ANTERIOR = {"nomedocumento", "numeroportariaanterior", "diaportariaanterior", "mesportariaanterior", "anoportariaanterior"}
DE_PESSOA = {n for n in PLACEHOLDERS if n.startswith(("nomegestor", "rsgestor", "nomefiscal", "rsfiscal"))}

_TOKEN = re.compile(r"(?<!&)#([A-Za-z]*)")
_ROMANO = re.compile(r"^(\s*)(X|IX|IV|V?I{0,3})(\s*[–—-])")
_ROMANOS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")


def usados(html: str) -> set[str]:
    """Placeholders (minúsculos) presentes no HTML."""
    return {m.group(1).lower() for m in _TOKEN.finditer(html or "")}


def invalidos(html: str, variante: str) -> list[str]:
    """Trechos `#...` que não são placeholders permitidos (ou que não cabem na variante)."""
    ruins: list[str] = []
    for m in _TOKEN.finditer(html or ""):
        nome = m.group(1).lower()
        if nome not in PLACEHOLDERS or (variante == "sem_anterior" and nome in DA_ANTERIOR):
            ruins.append(m.group(0) or "#")
    return list(dict.fromkeys(ruins))


def _renumerar(elementos: list) -> None:
    """Renumera os parágrafos consecutivos que começam com algarismo romano."""
    contador = 0
    for el in elementos:
        no = next((n for n in el.iter() if n.text and n.text.strip()), None)
        if no is None or not _ROMANO.match(no.text) or not _ROMANO.match(no.text).group(2):
            contador = 0
            continue
        no.text = _ROMANO.sub(lambda m: f"{m.group(1)}{_ROMANOS[contador]}{m.group(3)}", no.text, count=1) if contador < len(_ROMANOS) else no.text
        contador += 1


def preencher(html: str, valores: dict[str, str]) -> str:
    """HTML da máscara com os placeholders trocados; omite parágrafos de pessoa sem valor e renumera os incisos."""
    raiz = lxml_html.fragment_fromstring(html or "", create_parent="div")
    for el in list(raiz):
        texto = lxml_html.tostring(el, encoding="unicode")
        if any(n in DE_PESSOA and not valores.get(n) for n in usados(texto)):
            raiz.remove(el)
    _renumerar(list(raiz))
    corpo = "".join(lxml_html.tostring(el, encoding="unicode") for el in raiz)
    return _TOKEN.sub(lambda m: escape(valores.get(m.group(1).lower(), m.group(0))), corpo)
