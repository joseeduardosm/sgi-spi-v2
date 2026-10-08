# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar as tarefas recorrentes: datas da regra, criação da série, geração diária, gestão e permissões.
"""Tarefas recorrentes (`/api/tarefas/recorrencias` e `recorrencia` na criação)."""

from datetime import date, datetime, time, timezone

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.rh import Feriado
from app.models.tarefas import RecorrenciaTarefa, Tarefa
from app.services.tarefas import servico_recorrencias as sr
from tests.apoio_rh import simular_smtp
from tests.conftest import cabecalho, criar_usuario
from tests.test_tarefas import URL, equipe  # noqa: F401  (fixture da equipe)


@pytest.fixture(autouse=True)
def _smtp(monkeypatch):
    simular_smtp(monkeypatch)


def _lista(inicio: date, regra: sr.RegraRecorrencia, n: int, feriados: set[date] | None = None) -> list[date]:
    saida = []
    for data in sr.datas(inicio, regra, feriados or set()):
        saida.append(data)
        if len(saida) == n:
            break
    return saida


def test_datas_de_cada_frequencia():
    # Diária a cada 2 dias; semanal em segunda e quinta; mensal no dia 31; anual em 29/02
    assert _lista(date(2026, 11, 2), sr.RegraRecorrencia("diaria", 2), 3) == [date(2026, 11, 2), date(2026, 11, 4), date(2026, 11, 6)]
    assert _lista(date(2026, 11, 2), sr.RegraRecorrencia("semanal", 1, (0, 3)), 4) == [date(2026, 11, 2), date(2026, 11, 5), date(2026, 11, 9), date(2026, 11, 12)]
    assert _lista(date(2026, 11, 2), sr.RegraRecorrencia("semanal", 2, (0,)), 3) == [date(2026, 11, 2), date(2026, 11, 16), date(2026, 11, 30)]
    assert _lista(date(2027, 1, 31), sr.RegraRecorrencia("mensal", 1), 4) == [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]
    assert _lista(date(2028, 2, 29), sr.RegraRecorrencia("anual", 1), 3) == [date(2028, 2, 29), date(2029, 2, 28), date(2030, 2, 28)]
    # Fim da série
    assert _lista(date(2026, 11, 2), sr.RegraRecorrencia("diaria", 1, fim=date(2026, 11, 4)), 10) == [date(2026, 11, 2), date(2026, 11, 3), date(2026, 11, 4)]


def test_somente_dias_uteis_pula_fim_de_semana_e_feriado():
    regra = sr.RegraRecorrencia("diaria", 1, somente_dias_uteis=True)
    # 06/11/2026 é sexta; sábado e domingo vão para segunda 09/11; a segunda é feriado → terça 10/11
    assert _lista(date(2026, 11, 6), regra, 3, {date(2026, 11, 9)}) == [date(2026, 11, 6), date(2026, 11, 10), date(2026, 11, 11)]
    # Mensal no dia 15 de novembro (domingo em 2026) vai para segunda 16
    assert _lista(date(2026, 10, 15), sr.RegraRecorrencia("mensal", 1, somente_dias_uteis=True), 2) == [date(2026, 10, 15), date(2026, 11, 16)]


def test_descrever_a_regra():
    inicio = date(2026, 11, 2)
    assert sr.descrever(sr.RegraRecorrencia("semanal", 1, (0, 3), True, 1, date(2026, 12, 31)), inicio) == \
        "Toda semana, segunda-feira e quinta-feira, só em dias úteis, até 31/12/2026, criada 1 dia(s) antes do prazo"
    assert sr.descrever(sr.RegraRecorrencia("mensal", 3), inicio) == "A cada 3 meses, no dia 2"


def _corpo(equipe_id, ids, regra, prazo="2026-11-02T18:00:00-03:00", **extra):
    return {"titulo": "Relatório semanal", "descricao": "Fechar o relatório", "prazo": prazo, "equipe_id": equipe_id,
            "responsaveis_ids": [ids["ana"], ids["beto"]], "recorrencia": regra, **extra}


def test_previa_da_regra(cliente, equipe):
    ids, h, equipe_id = equipe
    r = cliente.post(f"{URL}/recorrencias/previa", json={"prazo": "2026-11-02T18:00:00-03:00", "regra": {"frequencia": "semanal", "dias_semana": [0, 3]}}, headers=h["ana"])
    assert r.status_code == 200 and r.json()["proximas"] == ["2026-11-05", "2026-11-09", "2026-11-12"] and r.json()["resumo"].startswith("Toda semana")
    assert cliente.post(f"{URL}/recorrencias/previa", json={"prazo": "2026-11-02T18:00:00-03:00", "regra": {"frequencia": "semanal"}}, headers=h["ana"]).status_code == 400
    assert cliente.post(f"{URL}/recorrencias/previa", json={"prazo": "2026-11-02T18:00:00-03:00", "regra": {"frequencia": "diaria", "fim": "2026-10-01"}}, headers=h["ana"]).status_code == 400
    assert cliente.post(f"{URL}/recorrencias/previa", json={"prazo": "2026-11-02T18:00:00-03:00", "regra": {"frequencia": "semanal", "dias_semana": [7]}}, headers=h["ana"]).status_code == 422


def test_cria_serie_e_gera_as_ocorrencias_pelo_calendario(cliente, equipe):
    ids, h, equipe_id = equipe
    regra = {"frequencia": "semanal", "dias_semana": [0], "antecedencia_dias": 1}
    r = cliente.post(URL, json=_corpo(equipe_id, ids, regra), headers=h["lia"])
    assert r.status_code == 201, r.text
    primeira = r.json()
    assert primeira["recorrencia"]["ativa"] and primeira["recorrencia"]["proxima_data"] == "2026-11-09" and primeira["recorrencia"]["ocorrencia_em"] == "2026-11-02"
    series = cliente.get(f"{URL}/recorrencias", params={"equipe_id": equipe_id}, headers=h["ana"]).json()
    assert len(series) == 1 and series[0]["geradas"] == 1 and series[0]["proximas"][:2] == ["2026-11-09", "2026-11-16"]

    with FabricaSessao() as s:
        # Antes de "prazo − antecedência" nada nasce; no dia 08/11 (domingo) nasce a de 09/11 (prazo 18:00 de Brasília)
        assert sr.gerar_ocorrencias(s, date(2026, 11, 7)) == {"criadas": 0, "puladas": 0, "pausadas_por_erro": 0}
        assert sr.gerar_ocorrencias(s, date(2026, 11, 8))["criadas"] == 1
        # Idempotente no mesmo dia
        assert sr.gerar_ocorrencias(s, date(2026, 11, 8))["criadas"] == 0
        tarefas = list(s.scalars(select(Tarefa).where(Tarefa.recorrencia_id.is_not(None)).order_by(Tarefa.numero)))
        assert [t.ocorrencia_em for t in tarefas] == [date(2026, 11, 2), date(2026, 11, 9)]
        nova = tarefas[1]
        assert nova.titulo == "Relatório semanal" and nova.responsavel_id == ids["ana"] and {r.usuario_id for r in nova.responsaveis} == {ids["ana"], ids["beto"]}
        assert nova.prazo.astimezone(sr.FUSO).strftime("%d/%m/%Y %H:%M") == "09/11/2026 18:00"
        # Parada longa: só a mais recente vencida é criada; as anteriores são puladas
        resultado = sr.gerar_ocorrencias(s, date(2026, 12, 1))
        assert resultado["criadas"] == 1 and resultado["puladas"] == 2
        ultimas = list(s.scalars(select(Tarefa.ocorrencia_em).where(Tarefa.recorrencia_id.is_not(None)).order_by(Tarefa.ocorrencia_em.desc()).limit(1)))
        assert ultimas == [date(2026, 11, 30)]  # 16/11 e 23/11 foram puladas; 07/12 só nasce em 06/12


def test_termina_pelo_numero_de_ocorrencias_e_pela_data(cliente, equipe):
    ids, h, equipe_id = equipe
    r = cliente.post(URL, json=_corpo(equipe_id, ids, {"frequencia": "diaria", "max_ocorrencias": 2}), headers=h["lia"])
    assert r.json()["recorrencia"]["proxima_data"] == "2026-11-03"
    with FabricaSessao() as s:
        assert sr.gerar_ocorrencias(s, date(2026, 11, 3))["criadas"] == 1
        assert sr.gerar_ocorrencias(s, date(2026, 11, 10))["criadas"] == 0
        rec = s.scalar(select(RecorrenciaTarefa))
        assert rec.proxima_data is None and rec.geradas == 2
    r = cliente.post(URL, json=_corpo(equipe_id, ids, {"frequencia": "diaria", "fim": "2026-11-02"}, titulo="Uma vez só"), headers=h["lia"])
    assert r.json()["recorrencia"]["proxima_data"] is None


def test_pausar_retomar_editar_e_excluir_com_permissoes(cliente, equipe):
    ids, h, equipe_id = equipe
    r = cliente.post(URL, json=_corpo(equipe_id, ids, {"frequencia": "diaria"}, prazo=datetime.now(timezone.utc).isoformat()), headers=h["ana"])
    rec_id = r.json()["recorrencia"]["id"]
    base = f"{URL}/recorrencias/{rec_id}"
    # Quem é de fora da equipe não vê; membro que não criou vê mas não altera; liderança e criador alteram
    assert cliente.get(base, headers=h["caio"]).status_code == 404
    assert cliente.get(base, headers=h["beto"]).json()["pode_gerir"] is False
    assert cliente.post(f"{base}/pausar", headers=h["beto"]).status_code == 403
    assert cliente.post(f"{base}/pausar", headers=h["lia"]).json()["ativa"] is False
    with FabricaSessao() as s:
        assert sr.gerar_ocorrencias(s, date(2099, 1, 1))["criadas"] == 0  # pausada não gera
    retomada = cliente.post(f"{base}/retomar", headers=h["ana"]).json()
    assert retomada["ativa"] and retomada["proxima_data"] is not None
    # Editar vale para as próximas: nova regra e responsáveis
    corpo = {"titulo": "Novo título", "descricao": "", "prioridade": "alta", "checklist": ["Conferir"], "responsaveis_ids": [ids["beto"]], "marcadores_ids": [],
             "regra": {"frequencia": "semanal", "dias_semana": [4]}}
    editada = cliente.put(base, json=corpo, headers=h["ana"]).json()
    assert editada["titulo"] == "Novo título" and editada["responsaveis"][0]["id"] == ids["beto"] and editada["resumo"].startswith("Toda semana, sexta-feira")
    assert cliente.put(base, json={**corpo, "responsaveis_ids": [ids["caio"]]}, headers=h["ana"]).status_code == 400  # Caio é de fora da equipe
    assert cliente.delete(base, headers=h["beto"]).status_code == 403
    assert cliente.delete(base, headers=h["lia"]).status_code == 204
    # As tarefas já criadas continuam, sem vínculo
    tarefa = cliente.get(f"{URL}/{r.json()['numero']}", headers=h["ana"]).json()
    assert tarefa["recorrencia"] is None


def test_serie_pausada_por_erro_avisa_quem_criou(cliente, equipe):
    ids, h, equipe_id = equipe
    cliente.post(URL, json=_corpo(equipe_id, ids, {"frequencia": "diaria"}), headers=h["lia"])
    # O responsável sai da equipe (fica inativo): a geração não consegue atribuir e pausa a série
    with FabricaSessao() as s:
        from app.models.usuario import Usuario

        s.get(Usuario, ids["ana"]).ativo = False
        s.commit()
        assert sr.gerar_ocorrencias(s, date(2026, 11, 3))["pausadas_por_erro"] == 1
        rec = s.scalar(select(RecorrenciaTarefa))
        assert not rec.ativa and "inativa" in rec.ultimo_erro.lower()
