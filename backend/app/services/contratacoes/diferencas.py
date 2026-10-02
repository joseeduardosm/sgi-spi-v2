# Criado por José Eduardo Santana Martins
# Este arquivo serve para comparar versões do documento: o que foi incluído, retirado, alterado e movido (estilo BookStack, por item).
"""Diferenças entre duas fotos do documento.

A foto (`VersaoDocumento.foto`) traz `secoes` e `itens` com id estável. Comparar por id dá: itens **incluídos**, **removidos**,
**alterados** (com a diferença por palavra em HTML: `<ins>` inserido, `<del>` retirado) e **movidos** (seção, pai ou posição).
"""

import difflib
import re
from html import escape

from app.services.contratacoes.conteudo import marcadores, texto_do_html


class _Item:
    """Item da foto, só com o que a numeração precisa."""

    def __init__(self, d: dict) -> None:
        self.id, self.pai_id, self.tipo, self.ordem = d["id"], d.get("pai_id"), d["tipo"], d["ordem"]


def _numeracao(foto: dict) -> dict[str, str]:
    """Marcador (`1.2.`) de cada item da foto, por id."""
    ordem_secao = {s["id"]: s["ordem"] for s in foto.get("secoes", [])}
    por_secao: dict[str, list] = {}
    for i in foto.get("itens", []):
        por_secao.setdefault(i["secao_id"], []).append(_Item(i))
    resultado: dict[str, str] = {}
    for secao_id, itens in por_secao.items():
        resultado.update({str(k): v for k, v in marcadores(ordem_secao.get(secao_id, 0), itens).items()})
    return resultado


def _palavras(texto: str) -> list[str]:
    return re.findall(r"\s+|[^\s]+", texto)


def diferenca_html(antes: str | None, depois: str | None) -> str:
    """Texto com `<ins>` (incluído) e `<del>` (retirado) por palavra; o texto é escapado."""
    a, b = _palavras(texto_do_html(antes or "")), _palavras(texto_do_html(depois or ""))
    saida: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            saida.append(escape("".join(a[i1:i2])))
            continue
        if i2 > i1:
            saida.append(f"<del>{escape(''.join(a[i1:i2]))}</del>")
        if j2 > j1:
            saida.append(f"<ins>{escape(''.join(b[j1:j2]))}</ins>")
    return "".join(saida).replace("\n", "<br>")


def comparar(antes: dict, depois: dict) -> dict:
    """Mudanças da foto `antes` para a foto `depois`: `{"resumo", "secoes", "itens", "metadados"}`."""
    ia, ib = {i["id"]: i for i in antes.get("itens", [])}, {i["id"]: i for i in depois.get("itens", [])}
    sa, sb = {s["id"]: s for s in antes.get("secoes", [])}, {s["id"]: s for s in depois.get("secoes", [])}
    na, nb = _numeracao(antes), _numeracao(depois)
    itens: list[dict] = []
    ordem_documento = {i["id"]: n for n, i in enumerate(depois.get("itens", []))}

    def secao_nome(idx: dict, secao_id: str) -> str:
        s = idx.get(secao_id)
        return f"{s['ordem']}. {s['titulo']}" if s else ""

    for item_id, novo in ib.items():
        velho = ia.get(item_id)
        if velho is None:
            itens.append({"id": item_id, "mudanca": "incluido", "marcador": nb.get(item_id, ""), "secao": secao_nome(sb, novo["secao_id"]),
                          "html": novo.get("conteudo_html") or novo.get("conteudo", ""), "tipo": novo["tipo"]})
            continue
        mudou_texto = (velho.get("conteudo_html") or velho.get("conteudo", "")) != (novo.get("conteudo_html") or novo.get("conteudo", ""))
        moveu = (velho["secao_id"], velho.get("pai_id"), velho["ordem"]) != (novo["secao_id"], novo.get("pai_id"), novo["ordem"])
        if mudou_texto or velho["tipo"] != novo["tipo"]:
            itens.append({"id": item_id, "mudanca": "alterado", "marcador": nb.get(item_id, ""), "marcador_antes": na.get(item_id, ""),
                          "secao": secao_nome(sb, novo["secao_id"]), "tipo": novo["tipo"],
                          "diferenca": diferenca_html(velho.get("conteudo_html") or velho.get("conteudo", ""), novo.get("conteudo_html") or novo.get("conteudo", ""))})
        elif moveu and na.get(item_id) != nb.get(item_id):
            itens.append({"id": item_id, "mudanca": "movido", "marcador": nb.get(item_id, ""), "marcador_antes": na.get(item_id, ""),
                          "secao": secao_nome(sb, novo["secao_id"]), "tipo": novo["tipo"],
                          "html": novo.get("conteudo_html") or novo.get("conteudo", "")})
    for item_id, velho in ia.items():
        if item_id not in ib:
            itens.append({"id": item_id, "mudanca": "removido", "marcador": na.get(item_id, ""), "secao": secao_nome(sa, velho["secao_id"]),
                          "html": velho.get("conteudo_html") or velho.get("conteudo", ""), "tipo": velho["tipo"]})
    itens.sort(key=lambda x: (ordem_documento.get(x["id"], 10**6), x["id"]))

    secoes: list[dict] = []
    for sid, nova in sb.items():
        velha = sa.get(sid)
        if velha is None:
            secoes.append({"id": sid, "mudanca": "incluida", "titulo": nova["titulo"], "ordem": nova["ordem"]})
        elif velha["titulo"] != nova["titulo"] or velha["ordem"] != nova["ordem"]:
            secoes.append({"id": sid, "mudanca": "alterada", "titulo": nova["titulo"], "titulo_antes": velha["titulo"], "ordem": nova["ordem"], "ordem_antes": velha["ordem"]})
    secoes += [{"id": sid, "mudanca": "removida", "titulo": s["titulo"], "ordem": s["ordem"]} for sid, s in sa.items() if sid not in sb]

    metadados = [{"campo": c, "antes": antes.get(c, ""), "depois": depois.get(c, "")} for c in ("nome", "processo", "situacao", "link_sei") if antes.get(c, "") != depois.get(c, "")]
    contagem = {k: sum(1 for i in itens if i["mudanca"] == k) for k in ("incluido", "removido", "alterado", "movido")}
    return {"resumo": {**contagem, "secoes": len(secoes), "metadados": len(metadados)}, "secoes": secoes, "itens": itens, "metadados": metadados}


def vazio() -> dict:
    return {"nome": "", "processo": "", "situacao": "", "link_sei": "", "secoes": [], "itens": [], "linhas_tabela": []}
