"""
===============================================================================
ARQUIVO: test_contratos_reajuste_mes_integral_api.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar, pela API, a escolha única do cálculo dos meses quebrados do
reajuste: o gestor escolhe pro rata ou integral.

RESUMO TÉCNICO:
Abre um reajuste com data de efeito no meio da competência 01/2026 já
medida e salva a memória (PUT /memoria) com e sem calculo_mes_quebrado.
Confere o resumo_meses (as duas opções calculadas período a período), o
bloqueio da geração dos arquivos (POST /memoria/arquivos) sem escolha, a
recusa da escolha quando não há mês quebrado e a prévia que não grava.

FINALIDADE DE NEGÓCIO:
A tela mostra as duas opções já calculadas e a memória de cálculo (PDF e
XLSX) só sai depois da escolha, que vale para todos os meses quebrados e
todos os itens. Isso evita memória gerada com critério indefinido e deixa o
gestor comparar o valor antes de decidir.

CONTEXTO NO SISTEMA:
Rotas de reajustes do contrato e servico_reajuste. Reaproveita o cenário de
test_contratos_retencao.py e os apoios de tests/apoio_contratos.py. As
funções de fração são testadas isoladamente em
test_contratos_reajuste_mes_cortado.py.

===============================================================================
"""

from datetime import date
from decimal import Decimal

from tests.apoio_contratos import definir_parametros, juntar_nf
# Fixtures importadas de outro arquivo de teste; o pytest as injeta pelo nome dos
# parâmetros (por isso os noqa F811).
from tests.test_contratos_retencao import _ambiente, cenario  # noqa: F401 - fixtures (competência 01/2026 medida, hoje = 15/03/2026)
from tests.test_contratos_execucao import _url


def _abrir(cliente, contrato, h, data_efeito="2026-01-15"):
    """Abre reajuste cuja data de efeito cai no meio da competência já medida (01/2026)."""
    painel = cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 1, "data_efeito": data_efeito}, headers=h).json()
    reajuste = painel["em_andamento"]
    return _url(contrato, f"/reajustes/{reajuste['id']}"), reajuste


def _corpo(reajuste, calculo=None):
    """Monta o corpo do PUT /memoria com 10% em todos os itens.

    Só inclui calculo_mes_quebrado quando informado (None = sem escolha).
    """
    corpo = {"itens": [{"item_id": i["item_id"], "indice_percentual": "10"} for i in reajuste["itens"]]}
    if calculo is not None:
        corpo["calculo_mes_quebrado"] = calculo
    return corpo


def _memoria(cliente, url, h, reajuste, calculo=None):
    """Salva a memória com 10% em todos os itens e a escolha indicada; devolve o reajuste."""
    resposta = cliente.put(f"{url}/memoria", json=_corpo(reajuste, calculo), headers=h)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["em_andamento"]


def _preparar(cliente, cenario, data_efeito="2026-01-15"):  # noqa: F811
    """Prepara o cenário comum: parâmetros com corte de alertas, NF juntada e reajuste aberto.

    Devolve (contrato, cabeçalho da gestora, url do reajuste, dados do reajuste).
    """
    contrato, base, gestora = cenario
    definir_parametros(corte_alertas_a_partir_de=date(2026, 9, 1))
    juntar_nf(cliente, base, gestora, "2105.00", "123")
    url, reajuste = _abrir(cliente, contrato, gestora, data_efeito)
    return contrato, gestora, url, reajuste


def test_mes_quebrado_traz_as_duas_opcoes_periodo_a_periodo(cliente, cenario):  # noqa: F811
    """Sem escolha, o resumo pede a decisão e traz pro rata (dois trechos) e integral (um trecho)."""
    contrato, gestora, url, reajuste = _preparar(cliente, cenario)
    resumo = _memoria(cliente, url, gestora, reajuste)["resumo_meses"]

    assert resumo["precisa_escolher"] is True and resumo["calculo_mes_quebrado"] is None
    (mes,) = resumo["meses_quebrados"]
    assert mes["competencia"] == "2026-01"
    pro_rata, integral = mes["opcoes"]["pro_rata"], mes["opcoes"]["integral"]
    trechos = pro_rata["itens"][0]["trechos"]
    assert [(t["inicio"], t["fim"], t["reajustado"]) for t in trechos][-1] == ("2026-01-15", "2026-01-31", True)
    assert trechos[0]["reajustado"] is False and trechos[0]["fim"] == "2026-01-14"
    assert len(integral["itens"][0]["trechos"]) == 1
    assert Decimal(integral["em_haver"]) > Decimal(pro_rata["em_haver"]) > 0
    assert Decimal(resumo["diferenca_integral"]) > Decimal(resumo["diferenca_pro_rata"])


def test_escolher_integral_grava_e_muda_a_diferenca(cliente, cenario):  # noqa: F811
    """Gravar integral faz a diferença retroativa ser a da opção integral e encerra a pendência de escolha."""
    contrato, gestora, url, reajuste = _preparar(cliente, cenario)
    antes = _memoria(cliente, url, gestora, reajuste)
    depois = _memoria(cliente, url, gestora, reajuste, "integral")

    assert Decimal(depois["diferenca_retroativa"]) == Decimal(antes["resumo_meses"]["diferenca_integral"])
    assert depois["resumo_meses"]["calculo_mes_quebrado"] == "integral"
    assert depois["resumo_meses"]["precisa_escolher"] is False


def test_memoria_so_e_gerada_depois_da_escolha(cliente, cenario):  # noqa: F811
    """Gerar os arquivos da memória sem a escolha dá 400; depois de escolher, dá 200."""
    contrato, gestora, url, reajuste = _preparar(cliente, cenario)
    _memoria(cliente, url, gestora, reajuste)
    sem_escolha = cliente.post(f"{url}/memoria/arquivos", headers=gestora)
    assert sem_escolha.status_code == 400, sem_escolha.text
    assert "meses quebrados" in sem_escolha.json()["detalhe"]

    _memoria(cliente, url, gestora, reajuste, "pro_rata")
    assert cliente.post(f"{url}/memoria/arquivos", headers=gestora).status_code == 200


def test_escolha_sem_mes_quebrado_e_recusada(cliente, cenario):  # noqa: F811
    """Efeito em 01/02: janeiro fica antes do efeito, nenhum mês quebrado, nada a escolher."""
    contrato, gestora, url, reajuste = _preparar(cliente, cenario, "2026-02-01")
    resposta = cliente.put(f"{url}/memoria", json=_corpo(reajuste, "integral"), headers=gestora)
    assert resposta.status_code == 400, resposta.text


def test_previa_mostra_a_escolha_sem_gravar(cliente, cenario):  # noqa: F811
    """A prévia com integral mostra diferença maior, mas o reajuste salvo continua sem escolha."""
    contrato, gestora, url, reajuste = _preparar(cliente, cenario)
    salvo = _memoria(cliente, url, gestora, reajuste)
    previa = cliente.post(f"{url}/memoria/previa", json=_corpo(reajuste, "integral"), headers=gestora)
    assert previa.status_code == 200, previa.text
    assert Decimal(previa.json()["diferenca_retroativa"]) > Decimal(salvo["diferenca_retroativa"])

    atual = cliente.get(_url(contrato, "/reajustes"), headers=gestora).json()["em_andamento"]
    assert atual["resumo_meses"]["calculo_mes_quebrado"] is None
