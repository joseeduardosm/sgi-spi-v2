"""
===============================================================================
ARQUIVO: extenso.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Escrever números, valores em reais e datas por extenso em português do
Brasil, sem dependência externa.

RESUMO TÉCNICO:
`inteiro` monta o texto em grupos de três dígitos (unidades, mil, milhões...)
usando `_ate_999`; `reais` separa reais e centavos; `data`, `mes_ano` e
`meses` formatam datas e prazos; `real` formata o valor numérico (R$ 1.234,56).

FINALIDADE DE NEGÓCIO:
Minutas de prorrogação e de reajuste exigem valores e prazos "por extenso"
(ex.: "R$ 1.200,00 (mil e duzentos reais)", "12 (doze) meses"), como é
praxe em documentos jurídicos da administração pública.

CONTEXTO NO SISTEMA:
Usado pelas máscaras e geradores de documentos de contratos (prorrogação,
reajuste, portarias) em `services/contratos/`.

===============================================================================
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_UNIDADES = ("zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze", "treze", "catorze",
             "quinze", "dezesseis", "dezessete", "dezoito", "dezenove")
_DEZENAS = ("", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa")
_CENTENAS = ("", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos")
_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
# (singular, plural) das ordens acima de mil
_ESCALAS = (("", ""), ("mil", "mil"), ("milhão", "milhões"), ("bilhão", "bilhões"), ("trilhão", "trilhões"))


def _ate_999(n: int) -> str:
    """Texto de 1 a 999 (ex.: 345 → "trezentos e quarenta e cinco").

    Caso especial: 100 é "cem"; de 101 a 199 a centena é "cento".
    """
    if n == 100:
        return "cem"
    partes = []
    if n >= 100:
        partes.append(_CENTENAS[n // 100])
        n %= 100
    if n >= 20:
        partes.append(_DEZENAS[n // 10] + (f" e {_UNIDADES[n % 10]}" if n % 10 else ""))
    elif n > 0:
        partes.append(_UNIDADES[n])
    return " e ".join(partes)


def inteiro(n: int) -> str:
    """Inteiro não negativo por extenso (ex.: 1250 → "mil duzentos e cinquenta")."""
    if n == 0:
        return "zero"
    # Quebra o número em grupos de 3 dígitos, do menor para o maior
    # (ex.: 1_250_300 → [300, 250, 1]); a posição do grupo é a "ordem" (mil, milhão...)
    grupos = []
    while n:
        grupos.append(n % 1000)
        n //= 1000
    textos = []
    for ordem, valor in enumerate(grupos):
        if not valor:
            continue
        # "mil", e não "um mil"
        if ordem == 1 and valor == 1:
            textos.append("mil")
            continue
        escala = _ESCALAS[ordem][0 if valor == 1 else 1]
        textos.append(f"{_ate_999(valor)} {escala}".strip())
    # Do maior bloco para o menor; "e" antes do último bloco quando ele é menor que 100 ou centena exata (mil e cem; um milhão e duzentos mil)
    textos.reverse()
    texto = textos[0]
    for atual in textos[1:]:
        ultimo = atual is textos[-1]
        texto += (" e " if ultimo and (grupos[0] < 100 or grupos[0] % 100 == 0) else " ") + atual
    return texto


def reais(valor: Decimal) -> str:
    """Valor em reais por extenso (ex.: 1.234,56 → "mil duzentos e trinta e quatro reais e cinquenta e seis centavos")."""
    # Trabalha em centavos inteiros (arredondando meio para cima) para evitar erro de casa decimal
    centavos_total = int((Decimal(valor) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    r, c = divmod(centavos_total, 100)
    partes = []
    if r:
        # Milhões exatos levam "de reais" (ex.: "dois milhões de reais")
        sufixo = "de reais" if r % 1_000_000 == 0 and r >= 1_000_000 else ("real" if r == 1 else "reais")
        partes.append(f"{inteiro(r)} {sufixo}")
    if c:
        partes.append(f"{inteiro(c)} {'centavo' if c == 1 else 'centavos'}")
    return " e ".join(partes) or "zero reais"


def real(valor: Decimal) -> str:
    """Valor em reais no formato brasileiro (R$ 1.234,56)."""
    return "R$ " + f"{Decimal(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def data(dia: date) -> str:
    """Data por extenso (ex.: 1º de novembro de 2026)."""
    return f"{'1º' if dia.day == 1 else dia.day} de {_MESES[dia.month - 1]} de {dia.year}"


def mes_ano(dia: date) -> str:
    """Mês e ano por extenso (ex.: novembro de 2026)."""
    return f"{_MESES[dia.month - 1]} de {dia.year}"


def meses(quantidade: int) -> str:
    """Prazo em meses no estilo jurídico (ex.: 12 → "12 (doze) meses")."""
    return f"{quantidade} ({inteiro(quantidade)}) {'mês' if quantidade == 1 else 'meses'}"
