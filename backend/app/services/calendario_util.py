# Criado por José Eduardo Santana Martins
# Este arquivo serve para contar e somar dias úteis (sem fins de semana e feriados do RH), usado por Contratos, Tarefas e SLA.
"""Dias úteis do portal: segunda a sexta, exceto os feriados cadastrados em `rh_feriados`."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rh import Feriado


def feriados_cadastrados(sessao: Session) -> set[date]:
    """Datas dos feriados cadastrados (todas as abrangências)."""
    return set(sessao.scalars(select(Feriado.data)))


def eh_util(dia: date, feriados: set[date]) -> bool:
    """Segunda a sexta que não é feriado."""
    return dia.weekday() < 5 and dia not in feriados


def somar_uteis(base: date, quantidade: int, feriados: set[date]) -> date:
    """`base` + N dias úteis (a própria `base`, se for útil, é o dia zero)."""
    dia, contados = base, 0
    while contados < quantidade:
        dia += timedelta(days=1)
        if eh_util(dia, feriados):
            contados += 1
    return dia


def uteis_entre(inicio: date, fim: date, feriados: set[date]) -> int:
    """Dias úteis completos de `inicio` (exclusive) a `fim` (inclusive): o dia de `inicio` não conta; mesmo dia ou `fim` antes de `inicio` = 0.

    É o inverso de `somar_uteis`: `uteis_entre(a, somar_uteis(a, n, f), f) == n`."""
    if fim <= inicio:
        return 0
    return sum(1 for i in range(1, (fim - inicio).days + 1) if eh_util(inicio + timedelta(days=i), feriados))
