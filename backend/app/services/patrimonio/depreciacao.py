# Criado por José Eduardo Santana Martins
# Este arquivo serve para calcular a depreciação linear dos bens (Política de Bens Móveis da Secretaria da Fazenda de SP).
"""Depreciação linear, mês a mês, a partir do mês seguinte ao bem ficar disponível para uso.

- valor depreciável = custo − valor residual
- depreciação mensal = valor depreciável ÷ vida útil em meses
- a depreciação **para** quando o bem chega ao valor residual (o bem continua ativo: fim de depreciação não autoriza baixa)
- bens de terceiros e bens culturais não depreciam
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENTAVOS = Decimal("0.01")


def _arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def meses_decorridos(disponivel_em: date, hoje: date) -> int:
    """Meses cheios de depreciação: começa no mês seguinte ao da disponibilidade (no próprio mês ainda é zero)."""
    return max(0, (hoje.year - disponivel_em.year) * 12 + (hoje.month - disponivel_em.month))


def depreciacao_mensal(custo: Decimal, residual_percentual: Decimal, vida_util_meses: int) -> Decimal:
    depreciavel = custo - custo * residual_percentual / Decimal(100)
    return depreciavel / Decimal(vida_util_meses)


def valor_calculado(
    custo: Decimal | None, residual_percentual: Decimal | None, vida_util_meses: int | None, disponivel_em: date | None, hoje: date, deprecia: bool = True,
) -> Decimal | None:
    """Valor atual calculado, ou o próprio custo se o bem não deprecia. Nulo quando faltam dados (sem custo, data ou vida útil)."""
    if custo is None:
        return None
    if not deprecia:
        return _arredondar(custo)
    if disponivel_em is None or not vida_util_meses or residual_percentual is None:
        return None
    meses = min(meses_decorridos(disponivel_em, hoje), vida_util_meses)
    residual = custo * residual_percentual / Decimal(100)
    # Nunca abaixo do residual
    return _arredondar(max(residual, custo - depreciacao_mensal(custo, residual_percentual, vida_util_meses) * meses))
