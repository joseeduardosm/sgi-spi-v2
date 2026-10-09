# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a competência atual e as etapas abertas mostradas como marcadores na carteira de contratos.
"""Carteira (`GET /api/contratos`): `competencia_atual` e `sem_competencias`."""

from datetime import date

import pytest

from tests.apoio_contratos import criar_contrato, restringir_contratos
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import _preparar_execucao, _url

HOJE = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    """Congela a data de hoje e baixa o corte de cobrança (as competências do teste são de 2026-01 a 2026-03)."""
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_competencias.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_painel.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_competencias.PENDENCIAS_A_PARTIR_DE", date(2000, 1, 1))


def _linha(cliente, h, contrato):
    itens = cliente.get("/api/contratos", params={"busca": contrato["numero"]}, headers=h).json()["itens"]
    return next(i for i in itens if i["id"] == contrato["id"])


def test_sem_competencias_e_depois_competencia_atual_com_etapa(cliente, admin):
    gestora = criar_usuario("gestora")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO"})
    h = cabecalho(cliente, "gestora")
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora})
    linha = _linha(cliente, h, contrato)
    assert linha["sem_competencias"] is True and linha["competencia_atual"] is None

    _preparar_execucao(cliente, contrato, h)
    assert cliente.post(_url(contrato, "/execucao/gerar"), headers=h).status_code == 200
    linha = _linha(cliente, h, contrato)
    atual = linha["competencia_atual"]
    assert linha["sem_competencias"] is False
    # A mais antiga ainda aberta é a de 01/2026: já passou do fim do período, sem medição iniciada
    assert atual["identificador"] == "2026-01" and atual["situacao"] == "disponivel" and atual["etapas"] == ["medicao"]
    # Fim de janeiro + 30 dias já passou em 15/03: atrasada
    assert atual["atrasada"] is True


def test_competencia_futura_fica_pendente_e_contrato_sem_atraso(cliente, admin, monkeypatch):
    gestora = criar_usuario("gestora")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO"})
    h = cabecalho(cliente, "gestora")
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora})
    _preparar_execucao(cliente, contrato, h)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=h)
    # No dia 10/01 a primeira competência (01/2026) ainda não terminou: pendente e sem atraso
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: date(2026, 1, 10))
    monkeypatch.setattr("app.services.contratos.servico_competencias.hoje", lambda: date(2026, 1, 10))
    monkeypatch.setattr("app.services.contratos.servico_painel.hoje", lambda: date(2026, 1, 10))
    atual = _linha(cliente, h, contrato)["competencia_atual"]
    assert atual["situacao"] == "pendente" and atual["etapas"] == ["medicao"] and atual["atrasada"] is False


def test_detalhe_do_contrato_continua_funcionando(cliente, admin):
    contrato = criar_contrato(cliente, admin)
    detalhe = cliente.get(f"/api/contratos/{contrato['id']}", headers=admin).json()
    assert detalhe["sem_competencias"] is True and detalhe["competencia_atual"] is None
