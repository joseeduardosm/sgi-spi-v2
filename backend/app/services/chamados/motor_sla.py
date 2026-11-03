# Criado por José Eduardo Santana Martins
# Este arquivo serve para calcular prazos de chamado em horas úteis (expediente do módulo + feriados do RH), sem acessar o banco.
"""Motor de horas úteis dos Chamados.

O prazo de um SLA só anda **dentro do expediente** (as faixas de horário de cada dia da semana) e **fora dos feriados** (vêm do RH,
`rh_feriados`; o ponto facultativo conta ou não conforme o parâmetro do módulo). Tudo é calculado no fuso de São Paulo e devolvido
em UTC, como o resto do banco.

Exemplo, com expediente de segunda a sexta das 8h às 18h: um chamado aberto na sexta às 17h com SLA de 4 horas vence na segunda
às 11h (1 hora na sexta + 3 horas na segunda). Aberto no sábado, começa a contar na segunda às 8h.

Funções puras (recebem o expediente e os feriados prontos), para o teste cobrir os casos difíceis sem banco:
- `somar_minutos_uteis(inicio, minutos, expediente, feriados)`: quando vence um prazo de N minutos úteis;
- `minutos_uteis_entre(inicio, fim, expediente, feriados)`: quantos minutos úteis há entre dois instantes (pausa do pendente, % do SLA);
- `fim_de_dias_uteis(inicio, dias, expediente, feriados)`: fim do expediente do N-ésimo dia útil seguinte (SLA em "dias").
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta

from app.core.banco import FUSO_SAO_PAULO

# Expediente: dia da semana (0 = segunda ... 6 = domingo) → faixas (início, fim) em ordem. Dia ausente = sem expediente.
Expediente = Mapping[int, Sequence[tuple[time, time]]]

# Limite de segurança: um expediente sem nenhuma faixa nunca venceria; o cálculo para em 10 anos de procura
LIMITE_DIAS = 3660


class ErroExpediente(ValueError):
    """Expediente sem nenhuma faixa de horário: não há como contar prazo."""


def _local(instante: datetime) -> datetime:
    """Instante no fuso de São Paulo (aceita UTC ou sem fuso, que é tratado como UTC, como o SQLite devolve)."""
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=UTC)
    return instante.astimezone(FUSO_SAO_PAULO)


def _faixas_do_dia(dia: date, expediente: Expediente, feriados: set[date]) -> list[tuple[datetime, datetime]]:
    """Faixas de trabalho do dia, já como instantes em São Paulo (vazio em feriado ou dia sem expediente)."""
    if dia in feriados:
        return []
    return [
        (datetime.combine(dia, inicio, FUSO_SAO_PAULO), datetime.combine(dia, fim, FUSO_SAO_PAULO))
        for inicio, fim in expediente.get(dia.weekday(), ())
    ]


def _validar(expediente: Expediente) -> None:
    if not any(expediente.get(d) for d in range(7)):
        raise ErroExpediente("O expediente não tem nenhuma faixa de horário.")


def somar_minutos_uteis(inicio: datetime, minutos: int, expediente: Expediente, feriados: set[date]) -> datetime:
    """Instante (UTC) em que se completam `minutos` úteis contados a partir de `inicio`.

    Se `inicio` cai fora do expediente, a contagem começa na próxima faixa. Zero minutos = o próprio início, ajustado para dentro
    do expediente (um chamado aberto no domingo com prazo zero vence na abertura de segunda)."""
    _validar(expediente)
    atual = _local(inicio)
    restante = max(0, minutos)
    dia = atual.date()
    for _ in range(LIMITE_DIAS):
        for comeco, fim in _faixas_do_dia(dia, expediente, feriados):
            if fim <= atual:
                continue
            ponto = max(comeco, atual)
            disponivel = int((fim - ponto).total_seconds() // 60)
            if restante <= disponivel:
                return (ponto + timedelta(minutes=restante)).astimezone(UTC)
            restante -= disponivel
        dia += timedelta(days=1)
    raise ErroExpediente("Prazo fora do limite de cálculo (verifique o expediente e os feriados).")


def minutos_uteis_entre(inicio: datetime, fim: datetime, expediente: Expediente, feriados: set[date]) -> int:
    """Minutos úteis entre dois instantes (0 se `fim` não for depois de `inicio`). É o inverso de `somar_minutos_uteis`."""
    _validar(expediente)
    a, b = _local(inicio), _local(fim)
    if b <= a:
        return 0
    total = 0.0
    dia = a.date()
    while dia <= b.date():
        for comeco, termino in _faixas_do_dia(dia, expediente, feriados):
            sobreposicao = (min(termino, b) - max(comeco, a)).total_seconds()
            if sobreposicao > 0:
                total += sobreposicao
        dia += timedelta(days=1)
    return int(total // 60)


def fim_de_dias_uteis(inicio: datetime, dias: int, expediente: Expediente, feriados: set[date]) -> datetime:
    """Fim do expediente do `dias`-ésimo dia útil depois do dia de `inicio` (o dia da abertura é o dia zero, como em `calendario_util`).

    Ex.: aberto na segunda às 10h, SLA de 2 dias = quarta no fim do expediente. Dia útil = dia com faixa de horário e sem feriado."""
    _validar(expediente)
    dia = _local(inicio).date()
    contados = 0
    for _ in range(LIMITE_DIAS):
        dia += timedelta(days=1)
        faixas = _faixas_do_dia(dia, expediente, feriados)
        if faixas:
            contados += 1
            if contados >= dias:
                return faixas[-1][1].astimezone(UTC)
    raise ErroExpediente("Prazo fora do limite de cálculo (verifique o expediente e os feriados).")


def proximo_dia_util(base: date, dias: int, expediente: Expediente, feriados: set[date]) -> date:
    """Data do `dias`-ésimo dia útil depois de `base` (para o prazo do "Não resolveu")."""
    _validar(expediente)
    dia, contados = base, 0
    for _ in range(LIMITE_DIAS):
        dia += timedelta(days=1)
        if _faixas_do_dia(dia, expediente, feriados):
            contados += 1
            if contados >= dias:
                return dia
    raise ErroExpediente("Prazo fora do limite de cálculo (verifique o expediente e os feriados).")


def prazo_do_sla(inicio: datetime, tempo: int, unidade: str, expediente: Expediente, feriados: set[date]) -> datetime:
    """Vencimento de um SLA (`minuto`, `hora` ou `dia`) contado a partir de `inicio`."""
    if unidade == "dia":
        return fim_de_dias_uteis(inicio, tempo, expediente, feriados)
    return somar_minutos_uteis(inicio, tempo * (60 if unidade == "hora" else 1), expediente, feriados)
