"""
===============================================================================
ARQUIVO: portaria_mascara.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Validar e preencher a máscara (modelo) da portaria de designação, um HTML
do editor rico com placeholders `#nome` de uma lista fechada.

RESUMO TÉCNICO:
- Validar (`invalidos`): qualquer `#` fora da lista (inclusive `#` solto ou
  `#015#`) barra o salvamento; a variante "sem_anterior" não pode usar os
  placeholders da portaria anterior (`DA_ANTERIOR`).
- Preencher (`preencher`): troca cada placeholder pelo valor (sempre
  escapado), omite parágrafo com placeholder de pessoa (nome ou RS) vazio e
  renumera em sequência os incisos em romano ("I -", "II -"...).
O HTML é manipulado com lxml (biblioteca de leitura/edição de HTML/XML).

FINALIDADE DE NEGÓCIO:
A portaria designa gestor, fiscais e suplentes do contrato. Há duas
variantes: com portaria anterior (substitui uma designação) e sem. Se um
papel não tiver pessoa (ex.: sem suplente), o inciso some e os demais são
renumerados, sem edição manual.

CONTEXTO NO SISTEMA:
Usado por `servico_portaria` para validar o modelo salvo na tela de Modelos
e para gerar o texto da portaria; o resultado vai para `portaria_documento`.
RS é o registro funcional do servidor.

===============================================================================
"""

import re
from html import escape

from lxml import html as lxml_html

# Variantes do modelo: com ou sem referência a uma portaria anterior
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
# Placeholders que só existem quando há portaria anterior
DA_ANTERIOR = {"nomedocumento", "numeroportariaanterior", "diaportariaanterior", "mesportariaanterior", "anoportariaanterior"}
# Placeholders de pessoa (nome/RS de gestor e fiscais): vazios fazem o parágrafo sumir
DE_PESSOA = {n for n in PLACEHOLDERS if n.startswith(("nomegestor", "rsgestor", "nomefiscal", "rsfiscal"))}

# Regex do placeholder: "#" seguido de letras. O `(?<!&)` ignora entidades HTML como "&#39;".
_TOKEN = re.compile(r"(?<!&)#([A-Za-z]*)")
# Início de parágrafo com algarismo romano de I a X seguido de travessão/hífen (grupos: espaço, número, traço)
_ROMANO = re.compile(r"^(\s*)(X|IX|IV|V?I{0,3})(\s*[–—-])")
_ROMANOS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")


def usados(html: str) -> set[str]:
    """Placeholders (minúsculos) presentes no HTML."""
    return {m.group(1).lower() for m in _TOKEN.finditer(html or "")}


def invalidos(html: str, variante: str) -> list[str]:
    """Trechos `#...` que não são placeholders permitidos (ou que não cabem na variante).

    Devolve a lista sem repetições; vazia significa que a máscara pode ser salva.
    `#` sozinho aparece como "#" na lista.
    """
    ruins: list[str] = []
    for m in _TOKEN.finditer(html or ""):
        nome = m.group(1).lower()
        if nome not in PLACEHOLDERS or (variante == "sem_anterior" and nome in DA_ANTERIOR):
            ruins.append(m.group(0) or "#")
    return list(dict.fromkeys(ruins))


def _renumerar(elementos: list) -> None:
    """Renumera os parágrafos consecutivos que começam com algarismo romano.

    Altera os elementos lxml no lugar. Um parágrafo que não começa com romano
    zera a contagem, então cada bloco de incisos recomeça em "I". Acima de X,
    o texto fica como está.
    """
    contador = 0
    for el in elementos:
        # Primeiro nó com texto do parágrafo (o romano pode estar dentro de um <strong>, por exemplo)
        no = next((n for n in el.iter() if n.text and n.text.strip()), None)
        if no is None or not _ROMANO.match(no.text) or not _ROMANO.match(no.text).group(2):
            contador = 0
            continue
        no.text = _ROMANO.sub(lambda m: f"{m.group(1)}{_ROMANOS[contador]}{m.group(3)}", no.text, count=1) if contador < len(_ROMANOS) else no.text
        contador += 1


def preencher(html: str, valores: dict[str, str]) -> str:
    """HTML da máscara com os placeholders trocados; omite parágrafos de pessoa sem valor e renumera os incisos."""
    # Envolve o fragmento num <div> para percorrer os parágrafos de primeiro nível
    raiz = lxml_html.fragment_fromstring(html or "", create_parent="div")
    # Remove os parágrafos que citam pessoa sem valor (ex.: suplente não designado)
    for el in list(raiz):
        texto = lxml_html.tostring(el, encoding="unicode")
        if any(n in DE_PESSOA and not valores.get(n) for n in usados(texto)):
            raiz.remove(el)
    _renumerar(list(raiz))
    # Só depois de remover e renumerar troca os placeholders (valores escapados; sem valor, fica como escrito)
    corpo = "".join(lxml_html.tostring(el, encoding="unicode") for el in raiz)
    return _TOKEN.sub(lambda m: escape(valores.get(m.group(1).lower(), m.group(0))), corpo)
