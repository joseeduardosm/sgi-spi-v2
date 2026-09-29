# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o reajuste com percentuais por item, o desconto e o crédito abatido nas medições.
"""Reajuste com desconto: percentuais positivos e negativos por item e crédito retroativo da SPI.

Contrato de apoio: item 1 contínuo (2 × R$ 1.000,00/mês) e item 2 sob demanda (R$ 10,50, 10 em janeiro).
"""

from datetime import date

import pytest

from app.core.banco import FabricaSessao
from app.models.contratos import AbatimentoReajuste
from tests.apoio_contratos import PDF, criar_contrato, restringir_contratos
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import _preparar_execucao, _url

HOJE = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    """Congela a data de hoje: janeiro e fevereiro já podem ser medidos."""
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_competencias.hoje", lambda: HOJE)


@pytest.fixture
def cenario(cliente, admin):
    """Contrato com execução gerada; devolve (contrato, cabeçalho da gestora, ids das NEs)."""
    gestora = criar_usuario("gestora")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora}, vigencia_maxima_meses=24)
    h = cabecalho(cliente, "gestora")
    _preparar_execucao(cliente, contrato, h)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=h)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=h).json()]
    return contrato, h, notas


def _competencia(cliente, contrato, h, identificador):
    return cliente.get(_url(contrato, f"/competencias/identificador/{identificador}"), headers=h).json()


def _medir(cliente, contrato, h, notas, identificador, quantidades=None):
    """Mede (previsto, ou as quantidades dadas por posição) e conclui a medição."""
    competencia = _competencia(cliente, contrato, h, identificador)
    base = _url(contrato, f"/competencias/{competencia['id']}")
    medidas = quantidades or [i["quantidade_prevista"] for i in competencia["itens"]]
    corpo = {"itens": [{"id": i["id"], "quantidade_medida": q} for i, q in zip(competencia["itens"], medidas, strict=True)],
             "notas_empenho_ids": notas}
    assert cliente.put(f"{base}/medicao", json=corpo, headers=h).status_code == 200
    cliente.post(f"{base}/medicao/ciencia", headers=h)
    r = cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _abrir(cliente, contrato, h, referencia, indices):
    """Abre o reajuste e grava os percentuais (um por item, na ordem)."""
    reajuste = cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 1, "mes_referencia": referencia}, headers=h).json()["em_andamento"]
    url = _url(contrato, f"/reajustes/{reajuste['id']}")
    itens = [{"item_id": i["item_id"], "indice_percentual": p} for i, p in zip(reajuste["itens"], indices, strict=True)]
    r = cliente.put(f"{url}/memoria", json={"itens": itens}, headers=h)
    return url, r


def _concluir(cliente, h, url):
    cliente.post(f"{url}/evidencia", files={"arquivo": ("ev.pdf", PDF)}, headers=h)
    assert cliente.post(f"{url}/memoria/arquivos", headers=h).status_code == 200
    r = cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_percentuais_por_item_positivo_negativo_e_limite(cliente, cenario):
    """Cada item com o seu percentual: +5% num e −3% no outro; −100% (preço zero) é recusado."""
    contrato, h, _ = cenario
    url, r = _abrir(cliente, contrato, h, "2026-02-01", ["5", "-3"])
    reajuste = r.json()["em_andamento"]
    assert [(i["indice_percentual"], i["valor_unitario_reajustado"]) for i in reajuste["itens"]] == [
        ("5.00000000", "1050.00"), ("-3.00000000", "10.19")]
    assert reajuste["diferenca_retroativa"] == "0.00" and reajuste["competencia_credito"] is None
    # Desconto geral de 10% ("aplicar a todos"): o mesmo percentual em todos os itens reduz a base
    itens = [{"item_id": i["item_id"], "indice_percentual": "-10"} for i in reajuste["itens"]]
    reajuste = cliente.put(f"{url}/memoria", json={"itens": itens}, headers=h).json()["em_andamento"]
    assert reajuste["base_reajustada"] == "1800.00" and reajuste["valor_global_reajustado"] < reajuste["valor_global_atual"]
    itens[0]["indice_percentual"] = "-100"
    assert cliente.put(f"{url}/memoria", json={"itens": itens}, headers=h).status_code == 422


def test_desconto_retroativo_vira_credito_abatido_na_proxima_medicao(cliente, cenario):
    """Janeiro medido; desconto de 10% desde janeiro: sem competência de diferença, crédito abatido em fevereiro."""
    contrato, h, notas = cenario
    _medir(cliente, contrato, h, notas, "2026-01")
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["-10", "0"])
    reajuste = r.json()["em_andamento"]
    # 2 postos medidos em janeiro × (900 − 1000)
    assert reajuste["diferenca_retroativa"] == "-200.00" and reajuste["competencia_credito"] == "02/2026"
    painel = _concluir(cliente, h, url)
    historico = painel["historico"][0]
    assert historico["diferenca_retroativa"] == "-200.00" and historico["competencia_diferenca"] is None
    assert historico["abatimentos"] == [{"competencia": "02/2026", "identificador": "2026-02", "medida": False, "valor": "200.00"}]
    assert cliente.get(_url(contrato, "/competencias/identificador/2026-01-dif"), headers=h).status_code == 404

    fevereiro = _competencia(cliente, contrato, h, "2026-02")
    assert fevereiro["itens"][0]["valor_unitario"] == "900.00"
    assert fevereiro["desconto_reajuste"] == "200.00" and fevereiro["descontos_reajuste"][0]["mes_referencia"] == "2026-01-01"
    medida = _medir(cliente, contrato, h, notas, "2026-02")
    # 2 × 900 = 1.800 medidos − 200 de crédito
    assert medida["total_medido"] == "1800.00" and medida["valor_autorizado"] == "1600.00" and medida["valor_a_pagar"] == "1600.00"


def test_credito_maior_que_a_medicao_passa_adiante_e_volta_na_reabertura(cliente, cenario):
    """Crédito de 200 com fevereiro medido em 90: abate 90, os 110 seguem para março; reabrir devolve."""
    contrato, h, notas = cenario
    _medir(cliente, contrato, h, notas, "2026-01")
    url, _ = _abrir(cliente, contrato, h, "2026-01-01", ["-10", "0"])
    _concluir(cliente, h, url)
    fevereiro = _medir(cliente, contrato, h, notas, "2026-02", ["0.1", "0"])
    assert fevereiro["total_medido"] == "90.00" and fevereiro["desconto_reajuste"] == "90.00" and fevereiro["valor_autorizado"] == "0.00"
    assert _competencia(cliente, contrato, h, "2026-03")["desconto_reajuste"] == "110.00"
    abatimentos = cliente.get(_url(contrato, "/reajustes"), headers=h).json()["historico"][0]["abatimentos"]
    assert [(a["competencia"], a["medida"], a["valor"]) for a in abatimentos] == [("02/2026", True, "90.00"), ("03/2026", False, "110.00")]

    r = cliente.post(_url(contrato, f"/competencias/{fevereiro['id']}/reabrir"), json={"etapa": "medicao", "justificativa": "Corrigir"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["desconto_reajuste"] == "200.00"
    assert _competencia(cliente, contrato, h, "2026-03")["desconto_reajuste"] == "0.00"


def test_credito_pendente_vai_para_a_proxima_competencia_gerada(cliente, cenario):
    """Crédito sem competência a medir (pendente) é vinculado quando a execução é gerada de novo."""
    contrato, h, notas = cenario
    _medir(cliente, contrato, h, notas, "2026-01")
    url, _ = _abrir(cliente, contrato, h, "2026-01-01", ["-10", "0"])
    _concluir(cliente, h, url)
    with FabricaSessao() as sessao:
        sessao.query(AbatimentoReajuste).update({"competencia_id": None})
        sessao.commit()
    assert cliente.get(_url(contrato, "/reajustes"), headers=h).json()["historico"][0]["credito_pendente"] == "200.00"
    cliente.post(_url(contrato, "/execucao/gerar"), headers=h)
    assert _competencia(cliente, contrato, h, "2026-02")["desconto_reajuste"] == "200.00"


def test_reajuste_misto_com_diferenca_liquida_positiva_gera_competencia_de_diferenca(cliente, cenario):
    """+10% no contínuo e −10% no sob demanda: diferença líquida positiva paga na competência "-dif"."""
    contrato, h, notas = cenario
    _medir(cliente, contrato, h, notas, "2026-01")
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "-10"])
    # 2 × (1100 − 1000) + 10 × (9,45 − 10,50)
    assert r.json()["em_andamento"]["diferenca_retroativa"] == "189.50"
    _concluir(cliente, h, url)
    diferenca = _competencia(cliente, contrato, h, "2026-01-dif")
    assert diferenca["total_medido"] == "189.50"
    assert [i["valor_unitario"] for i in diferenca["itens"]] == ["100.00", "-1.05"]
