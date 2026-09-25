"""Cálculos do módulo de contratos: datas de vigência, situação e valores.

Funções puras (sem banco), para que carteira, detalhe, previsão e execução usem exatamente a
mesma regra. Valores monetários em `Decimal`, arredondados com meio para cima (ROUND_HALF_UP).
"""

import calendar
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

CENTAVO = Decimal("0.01")
DIAS_A_VENCER = 90


class TipoItem(StrEnum):
    CONTINUO = "continuo"
    SOB_DEMANDA = "sob_demanda"


class Situacao(StrEnum):
    ATIVO = "ativo"
    A_VENCER = "a_vencer"
    ENCERRADO = "encerrado"
    SUSPENSO = "suspenso"


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def somar_meses(data: date, meses: int) -> date:
    """Soma meses mantendo o dia; se o mês de destino for mais curto, usa o último dia dele."""
    indice = data.month - 1 + meses
    ano, mes = data.year + indice // 12, indice % 12 + 1
    return date(ano, mes, min(data.day, calendar.monthrange(ano, mes)[1]))


def calcular_data_fim(inicio: date, meses: int) -> date:
    """Fim inclusivo de um prazo em meses: 01/01/2026 + 12 meses → 31/12/2026."""
    return somar_meses(inicio, meses) - timedelta(days=1)


def meses_em(inicio: date, fim: date) -> int:
    """Meses completos entre as datas (fim inclusivo). Períodos menores que um mês contam como 1."""
    if fim < inicio:
        return 0
    fim_exclusivo = fim + timedelta(days=1)
    meses = 0
    while somar_meses(inicio, meses + 1) <= fim_exclusivo:
        meses += 1
    return max(1, meses)


@dataclass(frozen=True)
class Vigencia:
    """Bloco fechado de vigência. Sequência 1 = inicial; 2, 3… = prorrogações em ordem de início."""

    sequencia: int
    inicio: date
    fim: date

    @property
    def meses(self) -> int:
        return meses_em(self.inicio, self.fim)


def montar_vigencias(
    data_inicio: date, data_fim: date, vigencia_inicial_meses: int, prorrogacoes: Iterable[tuple[date, date]] = ()
) -> list[Vigencia]:
    """Vigência inicial e uma vigência por prorrogação (`(inicio, novo_fim)`), em ordem.

    Sem prorrogações, `data_fim` do contrato é a fonte do fim (vale para dados importados).
    Com prorrogações, o primeiro bloco é reconstruído pela vigência inicial em meses.
    """
    termos = sorted(prorrogacoes)
    fim_inicial = data_fim if not termos else calcular_data_fim(data_inicio, vigencia_inicial_meses)
    vigencias = [Vigencia(1, data_inicio, fim_inicial)]
    vigencias += [Vigencia(indice, inicio, fim) for indice, (inicio, fim) in enumerate(termos, start=2)]
    return vigencias


def data_limite_maxima(data_inicio: date, vigencia_maxima_meses: int) -> date:
    return calcular_data_fim(data_inicio, vigencia_maxima_meses)


def calcular_situacao(data_fim: date, situacao_forcada: str | None, hoje: date) -> Situacao:
    if situacao_forcada:
        return Situacao(situacao_forcada)
    if hoje > data_fim:
        return Situacao.ENCERRADO
    return Situacao.A_VENCER if hoje + timedelta(days=DIAS_A_VENCER) >= data_fim else Situacao.ATIVO


@dataclass(frozen=True)
class ItemValor:
    """Dados do item necessários aos cálculos (desacoplado do modelo do banco)."""

    tipo: str
    quantidade_mensal: Decimal
    quantidade_total: Decimal
    valor_unitario: Decimal
    quantidade_executada: Decimal = Decimal(0)


def subtotal_mensal(item: ItemValor) -> Decimal:
    return item.quantidade_mensal * item.valor_unitario


def base_mensal(itens: Sequence[ItemValor]) -> Decimal:
    """Soma dos subtotais mensais dos itens contínuos (itens sob demanda não têm base fixa)."""
    return arredondar(sum((subtotal_mensal(i) for i in itens if i.tipo == TipoItem.CONTINUO), Decimal(0)))


def quantidade_acumulada(item: ItemValor, meses_vigencia: int, limite_sob_demanda: Decimal | None = None) -> Decimal:
    """Quantidade total da vigência: mensal × meses (contínuo) ou o limite da vigência (sob demanda)."""
    if item.tipo == TipoItem.SOB_DEMANDA:
        return item.quantidade_total if limite_sob_demanda is None else limite_sob_demanda
    return item.quantidade_mensal * meses_vigencia


def quantidade_disponivel(item: ItemValor, meses_vigencia: int, limite_sob_demanda: Decimal | None = None) -> Decimal:
    return max(Decimal(0), quantidade_acumulada(item, meses_vigencia, limite_sob_demanda) - item.quantidade_executada)


def valor_global(
    itens: Sequence[ItemValor],
    meses_vigencia_atual: int,
    limites_sob_demanda: Sequence[Decimal | None] | None = None,
    valor_reajustado: Decimal | None = None,
) -> Decimal:
    """Valor da vigência atual. Prorrogações anteriores não somam: cada vigência é um período próprio.

    Depois de um reajuste, vale a fotografia `valor_reajustado`. `limites_sob_demanda` traz, na
    mesma ordem de `itens`, o limite do item na vigência atual (nulo = quantidade total original).
    """
    if valor_reajustado is not None:
        return arredondar(valor_reajustado)
    limites = limites_sob_demanda or [None] * len(itens)
    total = sum(
        (quantidade_acumulada(item, meses_vigencia_atual, limite) * item.valor_unitario for item, limite in zip(itens, limites, strict=True)),
        Decimal(0),
    )
    return arredondar(total)


# ---------------------------------------------------------------------------------------------
# Períodos mensais e pró-rata (convenção comercial 30/360)
# ---------------------------------------------------------------------------------------------

FATOR = Decimal("0.00000001")


def primeiro_dia(data: date) -> date:
    return data.replace(day=1)


def ultimo_dia(data: date) -> date:
    return data.replace(day=calendar.monthrange(data.year, data.month)[1])


def dias_comerciais(inicio: date, fim: date) -> int:
    """Dias no mês pela convenção 30/360: o último dia civil de qualquer mês vale 30.

    Ex.: 15/01 a 31/01 = 16 dias (15 a 30); 01/02 a 28/02 = 30 dias; só 28/02 (último dia) = 1 dia.
    """
    dia_inicio = 30 if inicio == ultimo_dia(inicio) else min(inicio.day, 30)
    dia_fim = 30 if fim == ultimo_dia(fim) else min(fim.day, 30)
    return max(0, dia_fim - dia_inicio + 1)


@dataclass(frozen=True)
class PeriodoMensal:
    """Parte de um mês civil coberta por uma vigência."""

    competencia: date  # dia 1 do mês
    inicio: date
    fim: date
    sequencia_vigencia: int

    @property
    def fator(self) -> Decimal:
        """Fração do mês (1 = mês cheio)."""
        return (Decimal(dias_comerciais(self.inicio, self.fim)) / Decimal(30)).quantize(FATOR, rounding=ROUND_HALF_UP)


def meses_da_vigencia(vigencia: Vigencia) -> list[PeriodoMensal]:
    periodos = []
    mes = primeiro_dia(vigencia.inicio)
    while mes <= vigencia.fim:
        periodos.append(
            PeriodoMensal(mes, max(mes, vigencia.inicio), min(ultimo_dia(mes), vigencia.fim), vigencia.sequencia)
        )
        mes = somar_meses(mes, 1)
    return periodos


@dataclass(frozen=True)
class PeriodoExecucao:
    """Período de uma competência de execução: N meses civis (periodicidade), recortados pela vigência."""

    competencia: date
    inicio: date
    fim: date
    sequencia_vigencia: int
    meses: tuple[PeriodoMensal, ...]


def periodos_de_execucao(vigencias: Sequence[Vigencia], periodicidade_meses: int) -> list[PeriodoExecucao]:
    """Competências por mês civil: a 1ª começa no início da vigência; cada uma agrupa N meses."""
    periodos = []
    for vigencia in vigencias:
        meses = meses_da_vigencia(vigencia)
        for indice in range(0, len(meses), periodicidade_meses):
            grupo = tuple(meses[indice : indice + periodicidade_meses])
            periodos.append(PeriodoExecucao(grupo[0].competencia, grupo[0].inicio, grupo[-1].fim, vigencia.sequencia, grupo))
    return periodos


def quantidade_prevista_continua(quantidade_mensal: Decimal, calcula_pro_rata: bool, meses: Iterable[PeriodoMensal]) -> tuple[Decimal, Decimal]:
    """(quantidade prevista, fator em meses) de um item contínuo em um conjunto de meses.

    Com pró-rata, cada mês parcial conta pela fração 30/360; "sempre integral" conta mês cheio.
    """
    fator = sum(((m.fator if calcula_pro_rata else Decimal(1)) for m in meses), Decimal(0))
    return (quantidade_mensal * fator).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), fator
