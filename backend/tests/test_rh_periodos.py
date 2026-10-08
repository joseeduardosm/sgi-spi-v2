# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar os períodos aquisitivos de férias: crédito, expiração, saldo e avisos oficiais.
"""Períodos aquisitivos de férias (início dd/mm): limites, crédito automático, expiração, avisos e painel."""

from datetime import date

import pytest

from app.core.banco import FabricaSessao
from app.models.rh import PeriodoAquisitivo
from app.services.rh import servico_periodos
from app.tarefas import mensageria
from tests.apoio_rh import criar_cgp, funcionais, simular_smtp
from tests.conftest import cabecalho, criar_usuario
from tests.test_smtp import SmtpSimulado, dados_servidor

URL = "/api/rh/afastamentos"


class Relogio:
    dia = date(2026, 10, 1)


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    simular_smtp(monkeypatch)
    Relogio.dia = date(2026, 10, 1)
    monkeypatch.setattr("app.services.rh.servico_afastamentos.hoje", lambda: Relogio.dia)
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: Relogio.dia)


@pytest.fixture
def equipe(cliente, admin):
    ids = {login: criar_usuario(login, nome_completo=nome, email=f"{login}@sp.gov.br") for login, nome in (
        ("chefe", "Chefe Silva"), ("ana", "Ana Souza"), ("rh", "Rita RH"))}
    criar_cgp(ids["rh"])
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    return ids, {k: cabecalho(cliente, k) for k in ids}


def test_limites_do_periodo_inclusive_29_de_fevereiro():
    assert servico_periodos.limites(15, 3, date(2026, 10, 1)) == (date(2026, 3, 15), date(2027, 3, 14))
    assert servico_periodos.limites(15, 3, date(2026, 3, 14)) == (date(2025, 3, 15), date(2026, 3, 14))
    # 29/02: nos anos comuns vira 28/02
    assert servico_periodos.limites(29, 2, date(2026, 10, 1)) == (date(2026, 2, 28), date(2027, 2, 27))
    assert servico_periodos.limites(29, 2, date(2028, 3, 1)) == (date(2028, 2, 29), date(2029, 2, 27))
    assert servico_periodos.ler_inicio("15/03") == (15, 3) and servico_periodos.ler_inicio("") == (None, None)
    for invalido in ("31/04", "3/15", "abc", "15-03"):
        with pytest.raises(ValueError):
            servico_periodos.ler_inicio(invalido)


def test_cgp_informa_inicio_e_ajusta_o_periodo(cliente, equipe):
    ids, h = equipe
    url = f"/api/rh/cadastro/usuarios/{ids['ana']}"
    corpo = {"autorizador_id": ids["chefe"], "substituto_id": None, "sem_superior": False, "inicio_periodo_aquisitivo": "31/04",
             "exercicio": 2026, "saldo_lp_dias": 0}
    assert cliente.put(f"{url}/funcionais", json=corpo, headers=h["rh"]).status_code == 400
    # Sem início informado não dá para agendar férias
    r = cliente.post(URL, json={"tipo": "ferias", "inicio": "2026-11-03", "fim": "2026-11-12"}, headers=h["ana"])
    assert r.status_code == 400 and "início do seu período aquisitivo" in r.json()["detalhe"]
    r = cliente.put(f"{url}/funcionais", json={**corpo, "inicio_periodo_aquisitivo": "15/03"}, headers=h["rh"])
    assert r.status_code == 200 and r.json()["funcionais"]["inicio_periodo_aquisitivo"] == "15/03"
    periodo = r.json()["funcionais"]["periodos"][0]
    assert (periodo["inicio"], periodo["fim"], periodo["dias_creditados"], periodo["vigente"]) == ("2026-03-15", "2027-03-14", 30, True)
    # Ajuste da CGP (transição: 10 dias já gozados antes do sistema)
    r = cliente.put(f"{url}/periodo-vigente", json={"dias_creditados": 20}, headers=h["rh"])
    assert r.json()["funcionais"]["periodos"][0]["dias_creditados"] == 20 and r.json()["funcionais"]["periodos"][0]["origem"] == "ajuste_cgp"
    assert cliente.put(f"{url}/periodo-vigente", json={"dias_creditados": 20}, headers=h["ana"]).status_code == 403


def test_saldo_por_periodo_e_proximo_periodo(cliente, equipe):
    ids, h = equipe
    funcionais(ids["ana"], autorizador_id=ids["chefe"], inicio_aquisitivo_dia=15, inicio_aquisitivo_mes=3)
    assert cliente.post(URL, json={"tipo": "ferias", "inicio": "2026-11-03", "fim": "2026-11-22"}, headers=h["ana"]).status_code == 201
    r = cliente.post(URL, json={"tipo": "ferias", "inicio": "2027-01-05", "fim": "2027-01-15"}, headers=h["ana"])
    assert r.status_code == 400 and "15/03/2026 a 14/03/2027 insuficiente: 10 dia(s)" in r.json()["detalhe"]
    # O próximo período (a partir de 15/03/2027) tem saldo próprio
    assert cliente.post(URL, json={"tipo": "ferias", "inicio": "2027-03-16", "fim": "2027-04-14"}, headers=h["ana"]).status_code == 201
    r = cliente.post(URL, json={"tipo": "ferias", "inicio": "2028-03-21", "fim": "2028-03-30"}, headers=h["ana"])
    assert r.status_code == 400 and "vigente" in r.json()["detalhe"]
    meus = cliente.get(f"{URL}/meus", headers=h["ana"]).json()
    assert meus["saldos"]["ferias"] == {"saldo": 30, "usado": 20, "disponivel": 10}
    assert meus["periodo_vigente"]["fim"] == "2027-03-14" and meus["proximo_periodo"]["usado"] == 30


def test_credito_expiracao_e_avisos(cliente, equipe):
    ids, h = equipe
    funcionais(ids["ana"], autorizador_id=ids["chefe"], inicio_aquisitivo_dia=1, inicio_aquisitivo_mes=3)
    # Período 01/03/2026 a 28/02/2027, 30 dias; antecedência 30 + folga 15:
    # limite para começar 30/01/2027; limite para pedir 31/12/2026; 1º aviso 16/12/2026; lembrete 24/12; último 31/12
    with FabricaSessao() as sessao:
        periodo = servico_periodos.vigente(sessao, ids["ana"], date(2026, 12, 1))
        s = servico_periodos.situacao(sessao, periodo, date(2026, 12, 1))
        assert (s.data_limite_inicio, s.data_limite_pedido, s.data_aviso) == (date(2027, 1, 30), date(2026, 12, 31), date(2026, 12, 16))
        sessao.commit()
    SmtpSimulado.enviadas.clear()
    avisos = []
    for dia in (date(2026, 12, 15), date(2026, 12, 16), date(2026, 12, 17), date(2026, 12, 24), date(2026, 12, 31), date(2026, 12, 31)):
        Relogio.dia = dia
        with FabricaSessao() as sessao:
            avisos.append(servico_periodos.processar(sessao, dia)["avisos"])
    assert avisos == [0, 1, 0, 1, 1, 0]
    with FabricaSessao() as sessao:
        mensageria.enviar_emails_pendentes(sessao)
    assuntos = {(m["Subject"], para[0]) for m, _, para, _ in SmtpSimulado.enviadas}
    assert ("Férias a vencer: Ana Souza tem 30 dia(s) até 28/02/2027", "ana@sp.gov.br") in assuntos
    assert {para for _, para in assuntos} == {"ana@sp.gov.br", "chefe@sp.gov.br", "rh@sp.gov.br"}
    corpo = next(m for m, _, _, _ in SmtpSimulado.enviadas).get_body(("html",)).get_content()
    assert "cid:logo-sp" in corpo and "31/12/2026" in corpo
    # No início do novo período: crédito e expiração do saldo anterior
    Relogio.dia = date(2027, 3, 1)
    with FabricaSessao() as sessao:
        r = servico_periodos.processar(sessao, date(2027, 3, 1))
        assert r["creditos"] == 1 and r["expiracoes"] == 1
        anterior = sessao.query(PeriodoAquisitivo).filter_by(usuario_id=ids["ana"], inicio=date(2026, 3, 1)).one()
        assert anterior.dias_expirados == 30 and anterior.expirado_em is not None


def test_saldo_todo_agendado_nao_gera_aviso_e_painel_a_vencer(cliente, equipe):
    ids, h = equipe
    funcionais(ids["ana"], autorizador_id=ids["chefe"], inicio_aquisitivo_dia=1, inicio_aquisitivo_mes=3)
    Relogio.dia = date(2026, 12, 20)
    painel = cliente.get(f"{URL}/painel", params={"visao": "mensal", "ano": 2027, "mes": 1}, headers=h["chefe"]).json()
    assert [(x["nome"], x["disponivel"], x["data_limite_pedido"]) for x in painel["ferias_a_vencer"]] == [("Ana Souza", 30, "2026-12-31")]
    Relogio.dia = date(2026, 11, 20)
    assert cliente.post(URL, json={"tipo": "ferias", "inicio": "2027-01-05", "fim": "2027-02-03"}, headers=h["ana"]).status_code == 201
    Relogio.dia = date(2026, 12, 20)
    with FabricaSessao() as sessao:
        assert servico_periodos.processar(sessao, date(2026, 12, 20))["avisos"] == 0
    assert cliente.get(f"{URL}/painel", params={"visao": "mensal", "ano": 2027, "mes": 1}, headers=h["chefe"]).json()["ferias_a_vencer"] == []
