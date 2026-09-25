# Criado por José Eduardo Santana Martins
# Este arquivo serve para padronizar como valores em dinheiro e quantidades saem nas respostas da API.
"""Tipos decimais das respostas: sempre texto com casas fixas, igual em PostgreSQL e SQLite.

Dinheiro sai com 2 casas ("1234.50"), quantidade com 4 ("2.5000") e fatores/índices com 8.
Texto evita a perda de precisão de números de ponto flutuante no navegador.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer, WithJsonSchema


def _fixo(casas: str):
    return PlainSerializer(lambda valor: str(Decimal(valor).quantize(Decimal(casas))), return_type=str, when_used="json")


_TEXTO_DECIMAL = WithJsonSchema({"type": "string", "pattern": r"^-?\d+(\.\d+)?$"})

ValorMonetario = Annotated[Decimal, _fixo("0.01"), _TEXTO_DECIMAL]
ValorQuantidade = Annotated[Decimal, _fixo("0.0001"), _TEXTO_DECIMAL]
ValorFator = Annotated[Decimal, _fixo("0.00000001"), _TEXTO_DECIMAL]
