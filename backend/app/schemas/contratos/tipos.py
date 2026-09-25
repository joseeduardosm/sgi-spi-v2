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
    """Cria um serializador que arredonda o Decimal para as casas de `casas` e o devolve como texto.

    `when_used="json"`: só vale ao gerar JSON; dentro do Python o valor continua sendo Decimal.
    """
    return PlainSerializer(lambda valor: str(Decimal(valor).quantize(Decimal(casas))), return_type=str, when_used="json")


# Documenta na OpenAPI que esses campos chegam como texto numérico (ex.: "1234.50")
_TEXTO_DECIMAL = WithJsonSchema({"type": "string", "pattern": r"^-?\d+(\.\d+)?$"})

# Tipos prontos para usar nos schemas de resposta: dinheiro, quantidade e fator/índice
ValorMonetario = Annotated[Decimal, _fixo("0.01"), _TEXTO_DECIMAL]
ValorQuantidade = Annotated[Decimal, _fixo("0.0001"), _TEXTO_DECIMAL]
ValorFator = Annotated[Decimal, _fixo("0.00000001"), _TEXTO_DECIMAL]
