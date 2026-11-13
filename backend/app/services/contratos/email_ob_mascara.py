"""
===============================================================================
ARQUIVO: email_ob_mascara.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Validar e preencher a máscara (modelo) do e-mail de pagamento enviado aos
prepostos da contratada quando a Ordem Bancária (OB) é lançada no SGI.

RESUMO TÉCNICO:
Assunto e corpo (HTML do editor rico) usam placeholders de uma lista fechada,
com a mesma sintaxe do despacho e do e-mail de CADIN (`#nome`, `#nome#` ou
`##nome##`). Qualquer `#` fora da lista barra o salvamento; os valores são
sempre escapados; parágrafo com placeholder de pessoa vazio é omitido. A lista
é a do despacho mais os dados do pagamento (`valorpago`, `datapagamento`,
`horapagamento`, `usuarioob`).

FINALIDADE DE NEGÓCIO:
A OB é o documento que efetiva o pagamento à empresa. Avisar o preposto
(representante da contratada) com texto padronizado dá transparência ao
pagamento da competência e reduz pedidos de informação à equipe.

CONTEXTO NO SISTEMA:
Reaproveita `despacho_mascara`. O modelo padrão é semeado por migração e
editado em Contratos > Modelos; o envio fica no serviço de notificações,
disparado quando a OB é registrada na execução do contrato.

===============================================================================
"""

import re
from decimal import Decimal

from app.services.contratos import despacho_mascara

# Placeholders do despacho que não fazem sentido no e-mail (autoridade do despacho e vencimento da nota fiscal)
# A lista final é: os do despacho, menos os de `_FORA`, mais os do pagamento.
# O operador `|` entre dicionários junta os dois (o da direita prevalece em chave repetida).
_FORA = {"nomeautoridade", "cargoautoridade", "setorautoridade", "vencimentodanotafiscal"}

PLACEHOLDERS: dict[str, str] = {n: d for n, d in despacho_mascara.PLACEHOLDERS.items() if n not in _FORA} | {
    "valorpago": "Valor pago na competência: a soma das notas fiscais, em reais (ex.: R$ 12.345,67)",
    "datapagamento": "Dia em que a Ordem Bancária foi lançada no SGI (dd/mm/aaaa)",
    "horapagamento": "Hora em que a Ordem Bancária foi lançada no SGI (hh:mm)",
    "usuarioob": "Nome de quem lançou a Ordem Bancária no sistema",
}
# Placeholders que representam uma pessoa: com valor vazio, o parágrafo inteiro some do e-mail
DE_PESSOA = despacho_mascara.DE_PESSOA & set(PLACEHOLDERS)

_TOKEN = despacho_mascara._TOKEN  # noqa: SLF001 - mesma sintaxe do despacho


def usados(texto: str) -> set[str]:
    """Nomes de placeholders (em minúsculas) que aparecem no texto, válidos ou não."""
    return {m.group(1).lower() for m in _TOKEN.finditer(texto or "") if m.group(1)}


def invalidos(*textos: str) -> list[str]:
    """Trechos `#...` que não são placeholders permitidos, no assunto e no corpo.

    Devolve a lista sem repetições, na ordem em que apareceram; lista vazia
    significa que o modelo pode ser salvo.
    """
    ruins: list[str] = []
    for texto in textos:
        ruins += [m.group(0) or "#" for m in _TOKEN.finditer(texto or "") if m.group(1).lower() not in PLACEHOLDERS]
    return list(dict.fromkeys(ruins))


def preencher_html(html: str, valores: dict[str, str]) -> str:
    """Corpo preenchido (valores escapados; parágrafo de pessoa sem valor é omitido; placeholder sem valor fica como escrito)."""
    return despacho_mascara.preencher(html, valores)


def preencher_assunto(assunto: str, valores: dict[str, str]) -> str:
    """Assunto em texto simples, sem quebras de linha.

    Placeholder sem valor fica como escrito; espaços e quebras repetidos viram
    um só espaço, pois o assunto do e-mail precisa ser uma linha.
    """
    texto = _TOKEN.sub(lambda m: valores[m.group(1).lower()] if m.group(1).lower() in valores else m.group(0), assunto or "")
    return re.sub(r"\s+", " ", texto).strip()


def real(valor: Decimal) -> str:
    """Valor em reais no formato brasileiro (R$ 1.234,56).

    O Python formata no padrão americano (1,234.56); a troca em três passos usa
    "X" como marcador temporário para inverter vírgula e ponto.
    """
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def valores_do_pagamento(valores_despacho: dict[str, str], valor: Decimal, lancada_em, usuario: str, fuso) -> dict[str, str]:
    """Valores do despacho + os do pagamento (data e hora no horário de São Paulo).

    Parâmetros: `valor` (soma das notas fiscais pagas), `lancada_em` (momento em
    que a OB foi lançada), `usuario` (quem lançou) e `fuso` (São Paulo). Só
    devolve chaves que existem em `PLACEHOLDERS`.
    """
    # Data com fuso é convertida para São Paulo; sem fuso, é usada como está
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
