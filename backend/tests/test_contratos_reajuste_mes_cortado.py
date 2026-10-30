# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a fração da diferença no mês quebrado pela data de efeito, nos trechos
# da virada de vigência e no mês do fim da vigência, e a memória período a período do mês quebrado.
"""Reajuste: quanto de cada mês medido entra na diferença.

- Mês antes do efeito: nada (foi faturado antes de o reajuste valer).
- Mês quebrado (contém o efeito): uma escolha para todos os meses e itens. Pro rata cobra só os dias a
  partir do efeito; integral cobra o mês inteiro com o preço novo.
- Trecho da virada de vigência: só o trecho da vigência do reajuste conta; o da anterior é de outro reajuste.
- Mês do fim da vigência: já vem medido só até o último dia dela.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.contratos.servico_reajuste import _fracao_apos_efeito, _trechos_do_item

EFEITO = date(2026, 11, 15)
UM = Decimal(1)
ZERO = Decimal(0)


def competencia(inicio: date, fim: date) -> SimpleNamespace:
    return SimpleNamespace(competencia=inicio.replace(day=1), periodo_inicio=inicio, periodo_fim=fim)


def linha(*, pro_rata=True, inicio=None, vigencia=None, medida="30", preco="10") -> SimpleNamespace:
    return SimpleNamespace(calcula_pro_rata=pro_rata, periodo_inicio=inicio, sequencia_vigencia=vigencia,
                           quantidade_medida=Decimal(medida), valor_unitario=Decimal(preco))


def reajuste(*, efeito=EFEITO, modo=None) -> SimpleNamespace:
    """Reajuste da vigência 2 com a escolha do mês quebrado indicada (nula = ainda não escolhida)."""
    return SimpleNamespace(efeito=efeito, sequencia_vigencia=2, calculo_mes_quebrado=modo)


NOVEMBRO = competencia(date(2026, 11, 1), date(2026, 11, 30))
OUTUBRO = competencia(date(2026, 10, 1), date(2026, 10, 31))
DEZEMBRO = competencia(date(2026, 12, 1), date(2026, 12, 31))


def test_mes_antes_do_efeito_nao_entra():
    assert _fracao_apos_efeito(OUTUBRO, linha(), reajuste()) == ZERO


def test_mes_depois_do_efeito_entra_inteiro():
    assert _fracao_apos_efeito(DEZEMBRO, linha(), reajuste()) == UM


def test_pro_rata_cobra_so_os_dias_a_partir_do_efeito():
    """15 a 30/11 são 16 dos 30 dias comerciais; sem escolha gravada vale pro rata."""
    assert _fracao_apos_efeito(NOVEMBRO, linha(), reajuste()) == Decimal(16) / Decimal(30)
    assert _fracao_apos_efeito(NOVEMBRO, linha(), reajuste(modo="pro_rata")) == Decimal(16) / Decimal(30)


def test_integral_cobra_o_mes_inteiro():
    assert _fracao_apos_efeito(NOVEMBRO, linha(), reajuste(modo="integral")) == UM


def test_a_escolha_vale_tambem_para_item_sempre_integral():
    """No mês quebrado, a escolha manda: o item de faturamento sempre integral também é dividido em pro rata."""
    assert _fracao_apos_efeito(NOVEMBRO, linha(pro_rata=False), reajuste(modo="pro_rata")) == Decimal(16) / Decimal(30)


def test_modo_simula_sem_mudar_a_escolha_gravada():
    gravado = reajuste(modo="pro_rata")
    assert _fracao_apos_efeito(NOVEMBRO, linha(), gravado, "integral") == UM
    assert gravado.calculo_mes_quebrado == "pro_rata"


def test_mes_do_fim_da_vigencia_vai_so_ate_o_ultimo_dia():
    """Vigência até 10/02 e efeito em 05/02: pro rata = 05 a 10 sobre 01 a 10; integral = o período medido todo."""
    fevereiro = competencia(date(2027, 2, 1), date(2027, 2, 10))
    efeito = date(2027, 2, 5)
    assert _fracao_apos_efeito(fevereiro, linha(), reajuste(efeito=efeito)) == Decimal(6) / Decimal(10)
    assert _fracao_apos_efeito(fevereiro, linha(), reajuste(efeito=efeito, modo="integral")) == UM


def test_trecho_de_outra_vigencia_fica_de_fora():
    """Na virada de vigência, o trecho da vigência anterior é regido pelo reajuste dela."""
    virada = competencia(date(2026, 12, 1), date(2026, 12, 31))
    assert _fracao_apos_efeito(virada, linha(inicio=date(2026, 12, 1), vigencia=1), reajuste()) == ZERO
    assert _fracao_apos_efeito(virada, linha(inicio=date(2026, 12, 11), vigencia=2), reajuste()) == UM


def test_trechos_pro_rata_separam_valor_antigo_e_reajustado():
    """30 unidades a R$ 10,00, reajustado para R$ 11,00: 01–14 no preço antigo e 15–30 no novo."""
    antes, depois = _trechos_do_item(NOVEMBRO, linha(), Decimal("11"), reajuste(), "pro_rata")
    assert (antes["inicio"], antes["fim"], antes["dias"], antes["reajustado"]) == (date(2026, 11, 1), date(2026, 11, 14), 14, False)
    assert (antes["quantidade"], antes["valor_unitario"], antes["valor"]) == (Decimal(14), Decimal(10), Decimal("140.00"))
    assert (depois["inicio"], depois["fim"], depois["dias"], depois["reajustado"]) == (date(2026, 11, 15), date(2026, 11, 30), 16, True)
    assert depois["valor"] == Decimal("176.00")


def test_trecho_integral_e_o_mes_todo_reajustado():
    (unico,) = _trechos_do_item(NOVEMBRO, linha(), Decimal("11"), reajuste(), "integral")
    assert (unico["inicio"], unico["fim"], unico["dias"], unico["reajustado"]) == (date(2026, 11, 1), date(2026, 11, 30), 30, True)
    assert unico["valor"] == Decimal("330.00")
