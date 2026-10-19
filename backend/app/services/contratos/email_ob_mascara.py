# Criado por José Eduardo Santana Martins
# Este arquivo serve para validar e preencher a máscara (modelo) do e-mail de pagamento (OB) enviado aos prepostos da contratada.
"""Máscara do e-mail de pagamento: assunto e corpo (HTML do editor rico) com placeholders de uma **lista fechada**.

Mesma regra do despacho e do e-mail de CADIN: `#nome`, `#nome#` ou `##nome##`; qualquer `#` que não seja da lista barra o salvamento; os valores são
sempre escapados; parágrafo com placeholder de pessoa vazio é omitido. A lista é a do despacho (contrato, empresa, competência e equipe) **mais** os
dados do pagamento (`valorpago`, `datapagamento`, `horapagamento`, `usuarioob`).
"""

import re
from decimal import Decimal

from app.services.contratos import despacho_mascara

# Placeholders do despacho que não fazem sentido no e-mail (autoridade do despacho e vencimento da nota fiscal)
_FORA = {"nomeautoridade", "cargoautoridade", "setorautoridade", "vencimentodanotafiscal"}

PLACEHOLDERS: dict[str, str] = {n: d for n, d in despacho_mascara.PLACEHOLDERS.items() if n not in _FORA} | {
    "valorpago": "Valor pago na competência: a soma das notas fiscais, em reais (ex.: R$ 12.345,67)",
    "datapagamento": "Dia em que a Ordem Bancária foi lançada no SGI (dd/mm/aaaa)",
    "horapagamento": "Hora em que a Ordem Bancária foi lançada no SGI (hh:mm)",
    "usuarioob": "Nome de quem lançou a Ordem Bancária no sistema",
}
DE_PESSOA = despacho_mascara.DE_PESSOA & set(PLACEHOLDERS)

_TOKEN = despacho_mascara._TOKEN  # noqa: SLF001 - mesma sintaxe do despacho


def usados(texto: str) -> set[str]:
    return {m.group(1).lower() for m in _TOKEN.finditer(texto or "") if m.group(1)}


def invalidos(*textos: str) -> list[str]:
    """Trechos `#...` que não são placeholders permitidos, no assunto e no corpo."""
    ruins: list[str] = []
    for texto in textos:
        ruins += [m.group(0) or "#" for m in _TOKEN.finditer(texto or "") if m.group(1).lower() not in PLACEHOLDERS]
    return list(dict.fromkeys(ruins))


def preencher_html(html: str, valores: dict[str, str]) -> str:
    """Corpo preenchido (valores escapados; parágrafo de pessoa sem valor é omitido; placeholder sem valor fica como escrito)."""
    return despacho_mascara.preencher(html, valores)


def preencher_assunto(assunto: str, valores: dict[str, str]) -> str:
    """Assunto em texto simples, sem quebras de linha."""
    texto = _TOKEN.sub(lambda m: valores[m.group(1).lower()] if m.group(1).lower() in valores else m.group(0), assunto or "")
    return re.sub(r"\s+", " ", texto).strip()


def real(valor: Decimal) -> str:
    """Valor em reais no formato brasileiro (R$ 1.234,56)."""
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def valores_do_pagamento(valores_despacho: dict[str, str], valor: Decimal, lancada_em, usuario: str, fuso) -> dict[str, str]:
    """Valores do despacho + os do pagamento (data e hora no horário de São Paulo)."""
    quando = lancada_em.astimezone(fuso) if lancada_em.tzinfo else lancada_em
    return {**{k: v for k, v in valores_despacho.items() if k in PLACEHOLDERS}, "valorpago": real(valor), "datapagamento": f"{quando:%d/%m/%Y}",
            "horapagamento": f"{quando:%H:%M}", "usuarioob": usuario}


# Texto inicial do modelo que a migração semeia (a administração edita em Contratos › Modelos)
ASSUNTO_PADRAO = "Contrato #nrocontrato - #mescompetencia - Pagamento efetuado"
HTML_PADRAO = (
    "<p>Prezados,</p>"
    "<p>Informamos que a competência <b>#mescompetencia</b> do contrato <b>#nrocontrato</b> (#razaosocialempresa, CNPJ #cnpjempresa), "
    "no valor de <b>#valorpago</b>, foi paga em <b>#datapagamento</b>.</p>"
    "<p>A Ordem Bancária foi registrada no SGI SPI por #usuarioob.</p>"
    "<p>Atenciosamente,<br/>Secretaria de Parcerias em Investimentos</p>"
)
