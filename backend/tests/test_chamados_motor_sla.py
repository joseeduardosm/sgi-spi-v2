# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o motor de horas úteis dos Chamados (expediente, feriados do RH e fim de semana).
"""Motor de horas úteis (`app.services.chamados.motor_sla`), com os casos que o GLPI errava ou que a SPI tinha errado na configuração:
sexta → segunda, abertura fora do expediente, feriado no meio, SLA em dias e o inverso (minutos úteis entre dois instantes)."""

from datetime import UTC, date, datetime, time

import pytest

from app.core.banco import FUSO_SAO_PAULO
from app.services.chamados import motor_sla

# Segunda a sexta, das 8h às 18h (10 horas por dia)
COMERCIAL = {d: [(time(8), time(18))] for d in range(5)}
# Com almoço: 8h–12h e 13h–17h
COM_ALMOCO = {d: [(time(8), time(12)), (time(13), time(17))] for d in range(5)}


def sp(ano: int, mes: int, dia: int, hora: int = 0, minuto: int = 0) -> datetime:
    """Instante em São Paulo."""
    return datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO_SAO_PAULO)


def em_sp(instante: datetime) -> datetime:
    return instante.astimezone(FUSO_SAO_PAULO).replace(tzinfo=None)


# 2026-11-06 é sexta; 2026-11-09 é segunda
def test_sexta_a_tarde_vence_na_segunda():
    prazo = motor_sla.somar_minutos_uteis(sp(2026, 11, 6, 17), 4 * 60, COMERCIAL, set())
    assert em_sp(prazo) == datetime(2026, 11, 9, 11)


def test_aberto_no_sabado_comeca_na_segunda():
    prazo = motor_sla.somar_minutos_uteis(sp(2026, 11, 7, 10), 30, COMERCIAL, set())
    assert em_sp(prazo) == datetime(2026, 11, 9, 8, 30)


def test_aberto_antes_do_expediente_comeca_as_8h():
    prazo = motor_sla.somar_minutos_uteis(sp(2026, 11, 9, 6), 15, COMERCIAL, set())
    assert em_sp(prazo) == datetime(2026, 11, 9, 8, 15)


def test_feriado_do_rh_e_pulado():
    # 2026-11-20 (sexta) feriado: aberto quinta 17h com 2 horas → 1h na quinta, sexta pula, 1h na segunda
    prazo = motor_sla.somar_minutos_uteis(sp(2026, 11, 19, 17), 120, COMERCIAL, {date(2026, 11, 20)})
    assert em_sp(prazo) == datetime(2026, 11, 23, 9)


def test_intervalo_de_almoco_nao_conta():
    prazo = motor_sla.somar_minutos_uteis(sp(2026, 11, 9, 11), 120, COM_ALMOCO, set())
    assert em_sp(prazo) == datetime(2026, 11, 9, 14)


def test_minutos_uteis_entre_e_o_inverso_da_soma():
    inicio = sp(2026, 11, 6, 15, 20)
    for minutos in (0, 1, 59, 240, 600, 1500):
        assert motor_sla.minutos_uteis_entre(inicio, motor_sla.somar_minutos_uteis(inicio, minutos, COMERCIAL, set()), COMERCIAL, set()) == minutos


def test_pendente_no_fim_de_semana_nao_conta_tempo():
    # Pendente de sexta 17h a segunda 9h = 1h (sexta) + 1h (segunda)
    assert motor_sla.minutos_uteis_entre(sp(2026, 11, 6, 17), sp(2026, 11, 9, 9), COMERCIAL, set()) == 120


def test_sla_em_dias_vence_no_fim_do_expediente():
    # Segunda 10h + 2 dias úteis = quarta, 18h
    prazo = motor_sla.prazo_do_sla(sp(2026, 11, 9, 10), 2, "dia", COMERCIAL, set())
    assert em_sp(prazo) == datetime(2026, 11, 11, 18)


def test_sla_em_horas_e_minutos():
    assert em_sp(motor_sla.prazo_do_sla(sp(2026, 11, 9, 8), 15, "minuto", COMERCIAL, set())) == datetime(2026, 11, 9, 8, 15)
    assert em_sp(motor_sla.prazo_do_sla(sp(2026, 11, 9, 16), 3, "hora", COMERCIAL, set())) == datetime(2026, 11, 10, 9)


def test_aceita_instante_sem_fuso_como_utc():
    # 20:00 UTC de sexta = 17:00 em São Paulo
    prazo = motor_sla.somar_minutos_uteis(datetime(2026, 11, 6, 20), 60, COMERCIAL, set())
    assert prazo == datetime(2026, 11, 6, 21, tzinfo=UTC)


def test_proximo_dia_util_pula_fim_de_semana_e_feriado():
    assert motor_sla.proximo_dia_util(date(2026, 11, 19), 1, COMERCIAL, {date(2026, 11, 20)}) == date(2026, 11, 23)


def test_expediente_vazio_e_recusado():
    with pytest.raises(motor_sla.ErroExpediente):
        motor_sla.somar_minutos_uteis(sp(2026, 11, 9, 8), 10, {}, set())
