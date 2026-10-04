# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar por poucos segundos o resultado dos slides, já que o cálculo percorre toda a carteira.
"""Cache em memória com validade curta (por processo)."""

import threading
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
VALIDADE_SEGUNDOS = 60
_guardado: dict[tuple, tuple[float, object]] = {}
_trava = threading.Lock()


def obter(chave: tuple, calcular: Callable[[], T]) -> T:
    """Devolve o valor guardado (se ainda válido) ou calcula e guarda."""
    agora = time.monotonic()
    with _trava:
        achado = _guardado.get(chave)
        if achado and agora - achado[0] < VALIDADE_SEGUNDOS:
            return achado[1]  # type: ignore[return-value]
    valor = calcular()
    with _trava:
        _guardado[chave] = (agora, valor)
    return valor


def limpar() -> None:
    """Esvazia o cache (usado nos testes)."""
    with _trava:
        _guardado.clear()
