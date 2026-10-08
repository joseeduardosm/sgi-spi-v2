# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o calendário de vencimentos de contratos (eventos, filtros, escopo "meus" e validação do período).
"""Calendário de vencimentos: `GET /api/contratos/calendario`."""

from datetime import date, datetime, timedelta, timezone

import pytest

from tests.apoio_contratos import juntar_nf
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_retencao import _ambiente, cenario  # noqa: F401 — fixtures (data fixa de 15/03/2026, SMTP simulado, medição concluída)

URL = "/api/contratos/calendario"


@pytest.fixture(autouse=True)
def _corte(monkeypatch):
    """A competência de teste é de janeiro de 2026: libera o corte de cobrança (como nos testes do painel)."""
    from app.services.contratos import servico_competencias

    monkeypatch.setattr(servico_competencias, "PENDENCIAS_A_PARTIR_DE", date(2026, 1, 1))


def _eventos(cliente, h, de="2026-01-01", ate="2026-12-31", **params):
    r = cliente.get(URL, params={"de": de, "ate": ate, **params}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["eventos"]


def test_fim_da_vigencia_e_prazo_de_48h_da_nf(cliente, cenario):
    contrato, base, gestora = cenario
    assert _eventos(cliente, gestora, de="2020-01-01", ate="2020-12-31") == []  # período sem nada
    # Vigência de 12 meses a partir de 01/01/2026: termina em 31/12/2026
    vigencia = _eventos(cliente, gestora, de="2026-12-01", ate="2026-12-31", tipos="vigencia_fim")
    assert [e["data"] for e in vigencia] == ["2026-12-31"] and vigencia[0]["contrato_numero"] == contrato["numero"]
    # O prazo de 48 h conta da conclusão da medição (agora, no teste): cai hoje ou nos próximos dias
    agora = datetime.now(timezone.utc).date()
    prazos = _eventos(cliente, gestora, de=str(agora - timedelta(days=1)), ate=str(agora + timedelta(days=4)), tipos="prazo_nf_48h")
    assert len(prazos) == 1 and prazos[0]["hora"] is not None and prazos[0]["rota"].endswith("/execucao/2026-01")
    # Depois de juntar a NF o prazo de 48 h some
    assert juntar_nf(cliente, base, gestora, "2105.00", "123", recebida_em="2026-02-05", prazo="30").status_code == 200
    assert _eventos(cliente, gestora, de=str(agora - timedelta(days=1)), ate=str(agora + timedelta(days=4)), tipos="prazo_nf_48h") == []


def test_pagamento_da_nf_vira_evento_com_gravidade_pelo_atraso(cliente, cenario):
    contrato, base, gestora = cenario
    assert juntar_nf(cliente, base, gestora, "2105.00", "123", recebida_em="2026-02-05", prazo="30").status_code == 200
    eventos = _eventos(cliente, gestora, de="2026-03-01", ate="2026-03-31", tipos="pagamento_nf")
    assert len(eventos) == 1 and eventos[0]["data"] == "2026-03-07" and eventos[0]["severidade"] == "alta"  # "hoje" do teste: 15/03/2026


def test_meus_e_validacao_do_periodo(cliente, admin, cenario):
    contrato, base, gestora = cenario
    # A gestora integra a equipe: com `meus` continua vendo o contrato; o período e os tipos são validados
    assert _eventos(cliente, gestora, de="2026-12-01", ate="2026-12-31", tipos="vigencia_fim", meus="true")
    assert cliente.get(URL, params={"de": "2020-01-01", "ate": "2035-12-31"}, headers=gestora).status_code == 422  # mais de 366 dias
    assert cliente.get(URL, params={"de": "2026-02-01", "ate": "2026-01-01"}, headers=gestora).status_code == 422
    assert cliente.get(URL, params={"de": "2026-01-01", "ate": "2026-12-31", "tipos": "inventado"}, headers=gestora).status_code == 422
    # Quem não tem ACL de leitura em contratos não acessa
    criar_usuario("sem_acesso", email="sem@sp.gov.br")
    assert cliente.get(URL, params={"de": "2026-01-01", "ate": "2026-12-31"}, headers=cabecalho(cliente, "sem_acesso")).status_code == 403
