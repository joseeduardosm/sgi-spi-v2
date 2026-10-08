# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar os dias úteis, o cálculo do SLA e a política de SLA (Tarefas e Melhorias).
"""SLA de prazos: `calendario_util`, `servico_sla` e `/api/sla/politicas`."""

import uuid
from datetime import date, datetime, timezone

from app.services import calendario_util as util
from app.services.sla import servico_sla
from tests.conftest import cabecalho, criar_usuario
from tests.test_tarefas import URL, equipe  # noqa: F401  (fixture da equipe)
from tests.test_tarefas_desempenho import _cenario

SEGUNDA = date(2026, 10, 5)  # segunda-feira


def _em(dia: date, hora: int = 15) -> datetime:
    """15:00 UTC = 12:00 em São Paulo (mesmo dia)."""
    return datetime(dia.year, dia.month, dia.day, hora, 0, tzinfo=timezone.utc)


# --- Dias úteis -----------------------------------------------------------------------------------------

def test_somar_e_contar_dias_uteis_com_fim_de_semana_e_feriado():
    assert util.somar_uteis(date(2026, 10, 9), 1, set()) == date(2026, 10, 12)  # sexta + 1 útil = segunda
    assert util.somar_uteis(date(2026, 10, 9), 1, {date(2026, 10, 12)}) == date(2026, 10, 13)  # feriado na segunda
    assert util.somar_uteis(SEGUNDA, 0, set()) == SEGUNDA
    for n in (0, 1, 3, 8):
        assert util.uteis_entre(SEGUNDA, util.somar_uteis(SEGUNDA, n, {date(2026, 10, 7)}), {date(2026, 10, 7)}) == n  # é o inverso de somar_uteis
    assert util.uteis_entre(SEGUNDA, SEGUNDA, set()) == 0 and util.uteis_entre(date(2026, 10, 9), SEGUNDA, set()) == 0
    assert util.eh_util(date(2026, 10, 10), set()) is False  # sábado


# --- Cálculo (função pura) -----------------------------------------------------------------------------

def test_situacao_do_prazo_aberto_em_risco_e_estourado():
    politica = (1, 3)  # respostas até terça; resolução até quinta
    abertas = {hoje: servico_sla.calcular(_em(SEGUNDA), None, None, politica, set(), hoje) for hoje in (date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8), date(2026, 10, 9))}
    item = abertas[date(2026, 10, 6)]
    assert (item.prazo_resposta, item.prazo_resolucao) == (date(2026, 10, 6), date(2026, 10, 8))
    assert item.situacao_resposta == "em_risco"  # 1 de 1 dia útil consumido
    assert abertas[date(2026, 10, 7)].situacao_resposta == "estourado" and abertas[date(2026, 10, 7)].situacao_resolucao == "no_prazo"  # 2 de 3 = 67%
    assert abertas[date(2026, 10, 8)].situacao_resolucao == "em_risco"  # 3 de 3
    assert abertas[date(2026, 10, 9)].situacao_resolucao == "estourado"


def test_situacao_do_prazo_cumprido_dentro_e_fora():
    politica = (1, 3)
    no_prazo = servico_sla.calcular(_em(SEGUNDA), _em(date(2026, 10, 6)), _em(date(2026, 10, 8)), politica, set(), date(2026, 12, 1))
    assert (no_prazo.situacao_resposta, no_prazo.situacao_resolucao) == ("cumprido", "cumprido")
    fora = servico_sla.calcular(_em(SEGUNDA), _em(date(2026, 10, 7)), _em(date(2026, 10, 9)), politica, set(), date(2026, 12, 1))
    assert (fora.situacao_resposta, fora.situacao_resolucao) == ("cumprido_fora", "cumprido_fora")
    # Resolveu sem registrar o primeiro atendimento: respondeu, no mínimo, ao resolver
    assert servico_sla.calcular(_em(SEGUNDA), None, _em(date(2026, 10, 6)), politica, set(), date(2026, 12, 1)).situacao_resposta == "cumprido"
    # Feriado empurra o prazo
    com_feriado = servico_sla.calcular(_em(SEGUNDA), None, None, politica, {date(2026, 10, 6)}, date(2026, 10, 6))
    assert com_feriado.prazo_resposta == date(2026, 10, 7)


# --- Política e integração ----------------------------------------------------------------------------

def test_politica_lista_grava_e_exige_permissao(cliente, admin):
    r = cliente.get("/api/sla/politicas", headers=admin)
    assert r.status_code == 200
    padrao = {(p["modulo"], p["prioridade"]): (p["dias_uteis_resposta"], p["dias_uteis_resolucao"]) for p in r.json()}
    assert padrao[("tarefas", "critica")] == (1, 3) and padrao[("melhorias", "")] == (3, 15) and len(padrao) == 5
    nova = {"modulo": "tarefas", "prioridade": "critica", "dias_uteis_resposta": 1, "dias_uteis_resolucao": 2, "ativo": True}
    assert cliente.put("/api/sla/politicas", json={"politicas": [nova]}, headers=admin).status_code == 200
    linhas = {(p["modulo"], p["prioridade"]): p["dias_uteis_resolucao"] for p in cliente.get("/api/sla/politicas", headers=admin).json()}
    assert linhas[("tarefas", "critica")] == 2
    # Resolução menor que a resposta e combinação inexistente: 400
    assert cliente.put("/api/sla/politicas", json={"politicas": [{**nova, "dias_uteis_resposta": 5}]}, headers=admin).status_code == 400
    assert cliente.put("/api/sla/politicas", json={"politicas": [{**nova, "modulo": "melhorias"}]}, headers=admin).status_code == 400
    # O recurso `sla` nasce fechado (como na migração): só quem tem regra lê e grava
    gestor = criar_usuario("gestor_sla", email="gestor@sp.gov.br")
    criar_usuario("comum", email="comum@sp.gov.br")
    recurso = cliente.post("/api/acl/recursos", json={"nome": "SLA de prazos", "slug": "sla"}, headers=admin).json()["id"]
    assert cliente.post("/api/acl/regras", json={"recurso_id": recurso, "nivel": "LEITURA", "usuarios_ids": [gestor], "setores_ids": []}, headers=admin).status_code == 201
    assert cliente.get("/api/sla/politicas", headers=cabecalho(cliente, "gestor_sla")).status_code == 200
    assert cliente.put("/api/sla/politicas", json={"politicas": [nova]}, headers=cabecalho(cliente, "gestor_sla")).status_code == 403  # só leitura
    assert cliente.get("/api/sla/politicas", headers=cabecalho(cliente, "comum")).status_code == 403


def test_desempenho_traz_o_cumprimento_do_sla_e_a_tarefa_traz_a_situacao(cliente, equipe):
    ids, h, equipe_id = equipe
    _cenario(uuid.UUID(equipe_id), ids["ana"])
    d = cliente.get(f"{URL}/equipes/{equipe_id}/desempenho", params={"de": "2026-06-01", "ate": "2026-06-14"}, headers=h["lia"]).json()
    sla = d["sla"]
    # Prioridade normal: 3 dias úteis para responder e 10 para resolver. A e C resolvidas no prazo; E (11 dias úteis) fora
    assert (sla["resolucoes_no_prazo"], sla["resolucoes_fora"], sla["percentual_resolucao"]) == (2, 1, 66.7)
    assert (sla["respostas_no_prazo"], sla["respostas_fora"], sla["percentual_resposta"]) == (1, 1, 50.0)
    assert sla["abertas_estouradas"] == 1  # B nunca saiu de "a fazer"
    assert d["pessoas"][0]["sla_percentual"] == 66.7
    lista = cliente.get(URL, params={"escopo": "equipe", "equipe_id": equipe_id}, headers=h["lia"]).json()["itens"]
    tarefa_b = next(t for t in lista if t["numero"] == 102)
    assert tarefa_b["sla"]["situacao_resolucao"] == "estourado" and tarefa_b["sla"]["meta_resolucao_dias"] == 10
