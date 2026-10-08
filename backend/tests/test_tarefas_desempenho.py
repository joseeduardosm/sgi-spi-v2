# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o desempenho da equipe de tarefas (burndown, vazão, ciclo, fluxo acumulado e por pessoa).
"""Desempenho da equipe (`/api/tarefas/equipes/{id}/desempenho`)."""

import uuid
from datetime import date, datetime, timedelta, timezone

from app.core.banco import FabricaSessao
from app.models.tarefas import EventoTarefa, ResponsavelTarefa, Tarefa
from tests.test_tarefas import URL, equipe  # noqa: F401  (fixture da equipe)

# 12:00 em São Paulo = 15:00 UTC: as diferenças entre datas dão dias inteiros
def _em(ano, mes, dia) -> datetime:
    return datetime(ano, mes, dia, 15, 0, tzinfo=timezone.utc)


def _tarefa(sessao, equipe_id, numero, criada, status, responsavel, movimentos=(), **carimbos):
    """Tarefa com a linha do tempo informada: `movimentos` = [(data, de, para)] (vazio + carimbos = tarefa migrada, sem de/para)."""
    t = Tarefa(numero=numero, titulo=f"Tarefa {numero}", descricao="", equipe_id=equipe_id, criado_por_id=responsavel, responsavel_id=responsavel, prazo=criada + timedelta(days=60),
               prazo_original=criada + timedelta(days=60), status=status, criado_em=criada, atualizado_em=_em(2026, 6, 14), **carimbos)
    t.responsaveis = [ResponsavelTarefa(usuario_id=responsavel)]
    sessao.add(t)
    sessao.flush()
    for quando, de, para in movimentos:
        sessao.add(EventoTarefa(tarefa_id=t.id, tipo="status", autor_nome="x", titulo="mov", dados={"de": de, "para": para}, criado_em=quando))
    return t


def _cenario(equipe_id, ana) -> None:
    with FabricaSessao() as s:
        _tarefa(s, equipe_id, 101, _em(2026, 5, 20), "concluida", ana, [(_em(2026, 5, 25), "a_fazer", "em_andamento"), (_em(2026, 6, 3), "em_andamento", "concluida")],
                iniciada_em=_em(2026, 5, 25), concluida_em=_em(2026, 6, 3))                                       # A: aberta no início, conclui na semana 1
        _tarefa(s, equipe_id, 102, _em(2026, 5, 28), "a_fazer", ana)                                              # B: nunca sai de A fazer
        _tarefa(s, equipe_id, 103, _em(2026, 6, 3), "concluida", ana, [(_em(2026, 6, 4), "a_fazer", "em_andamento"), (_em(2026, 6, 10), "em_andamento", "concluida")],
                iniciada_em=_em(2026, 6, 4), concluida_em=_em(2026, 6, 10))                                       # C: nasce no período, conclui na semana 2
        _tarefa(s, equipe_id, 104, _em(2026, 5, 10), "concluida", ana, [(_em(2026, 5, 15), "em_andamento", "concluida")], concluida_em=_em(2026, 5, 15))  # D: concluída antes
        _tarefa(s, equipe_id, 105, _em(2026, 5, 25), "concluida", ana, iniciada_em=_em(2026, 6, 2), concluida_em=_em(2026, 6, 9))  # E: migrada, sem de/para
        s.commit()


def test_burndown_vazao_ciclo_fluxo_e_pessoas(cliente, equipe):
    ids, h, equipe_id = equipe
    _cenario(uuid.UUID(equipe_id), ids["ana"])
    r = cliente.get(f"{URL}/equipes/{equipe_id}/desempenho", params={"de": "2026-06-01", "ate": "2026-06-14"}, headers=h["lia"])
    assert r.status_code == 200, r.text
    d = r.json()
    b = d["burndown"]
    assert b["inicial"] == 3 and len(b["dias"]) == 14
    assert b["real"] == [3, 3, 3, 3, 3, 3, 3, 3, 2, 1, 1, 1, 1, 1]
    assert b["escopo"] == [3, 3] + [4] * 12
    assert b["ideal"][0] == 3.0 and b["ideal"][-1] == 0.0 and b["ideal"][1] == round(3 * 12 / 13, 2)
    assert [(v["criadas"], v["concluidas"], v["media_movel"]) for v in d["vazao"]] == [(1, 1, 1.0), (0, 2, 1.5)]
    c1, c2 = d["ciclo"]
    assert (c1["ciclo_mediana"], c1["lead_mediana"]) == (9.0, 14.0)
    assert (c2["ciclo_mediana"], c2["ciclo_p85"], c2["lead_mediana"], c2["lead_p85"]) == (6.5, 7.0, 11.0, 15.0)
    fluxo = d["fluxo"]
    assert fluxo["a_fazer"][-1] == 1 and fluxo["concluida"][-1] == 4 and fluxo["em_andamento"][4] == 2  # no dia 5 estão em andamento a C e a E (migrada)
    assert [{k: v for k, v in p.items() if k != "sla_percentual"} for p in d["pessoas"]] == [{"usuario_id": ids["ana"], "nome": "Ana Executora", "concluidas": 3, "lead_medio_dias": 12.0}]
    assert d["resumo"]["concluidas_no_periodo"] == 3 and d["resumo"]["criadas_no_periodo"] == 1 and d["resumo"]["abertas_agora"] == 1


def test_dias_futuros_ficam_sem_valor_e_permissoes(cliente, equipe):
    ids, h, equipe_id = equipe
    hoje = date.today()
    r = cliente.get(f"{URL}/equipes/{equipe_id}/desempenho", params={"de": hoje.isoformat(), "ate": (hoje + timedelta(days=3)).isoformat()}, headers=h["lia"])
    assert r.status_code == 200 and r.json()["burndown"]["real"][-1] is None
    # Padrão: últimos 30 dias; só a liderança vê; período inválido ou grande demais é recusado
    assert len(cliente.get(f"{URL}/equipes/{equipe_id}/desempenho", headers=h["lia"]).json()["burndown"]["dias"]) == 30
    assert cliente.get(f"{URL}/equipes/{equipe_id}/desempenho", headers=h["ana"]).status_code == 403
    assert cliente.get(f"{URL}/equipes/{equipe_id}/desempenho", params={"de": "2026-06-10", "ate": "2026-06-01"}, headers=h["lia"]).status_code == 400
    assert cliente.get(f"{URL}/equipes/{equipe_id}/desempenho", params={"de": "2025-01-01", "ate": "2026-06-01"}, headers=h["lia"]).status_code == 400
    assert cliente.get(f"{URL}/equipes/{uuid.uuid4()}/desempenho", headers=h["lia"]).status_code == 404


def test_conclusao_desfeita_pela_reabertura_nao_conta(cliente, equipe):
    """Tarefa concluída por engano e reaberta: sai da vazão, do ciclo, do lead time e do total por pessoa (reflete o estado real)."""
    ids, h, equipe_id = equipe
    with FabricaSessao() as s:
        # Concluída em 03/06 e reaberta em 05/06 (continua em andamento); outra concluída em 04/06, reaberta e concluída de novo em 09/06
        _tarefa(s, uuid.UUID(equipe_id), 201, _em(2026, 6, 1), "em_andamento", ids["ana"],
                [(_em(2026, 6, 2), "a_fazer", "em_andamento"), (_em(2026, 6, 3), "em_andamento", "concluida"), (_em(2026, 6, 5), "concluida", "em_andamento")])
        _tarefa(s, uuid.UUID(equipe_id), 202, _em(2026, 6, 1), "concluida", ids["ana"],
                [(_em(2026, 6, 2), "a_fazer", "em_andamento"), (_em(2026, 6, 4), "em_andamento", "concluida"), (_em(2026, 6, 5), "concluida", "em_andamento"),
                 (_em(2026, 6, 9), "em_andamento", "concluida")], concluida_em=_em(2026, 6, 9))
        s.commit()
    d = cliente.get(f"{URL}/equipes/{equipe_id}/desempenho", params={"de": "2026-06-01", "ate": "2026-06-14"}, headers=h["lia"]).json()
    assert [v["concluidas"] for v in d["vazao"]] == [0, 1]  # só a #202, na semana da última conclusão
    assert d["resumo"]["concluidas_no_periodo"] == 1 and d["resumo"]["abertas_agora"] == 1
    assert [{k: v for k, v in p.items() if k != "sla_percentual"} for p in d["pessoas"]] == [{"usuario_id": ids["ana"], "nome": "Ana Executora", "concluidas": 1, "lead_medio_dias": 8.0}]
    assert d["ciclo"][1]["lead_mediana"] == 8.0


def test_desempenho_de_uma_pessoa_inclui_tarefas_pessoais_e_respeita_a_visibilidade(cliente, equipe):
    ids, h, equipe_id = equipe
    with FabricaSessao() as s:
        _tarefa(s, uuid.UUID(equipe_id), 301, _em(2026, 6, 1), "concluida", ids["ana"], [(_em(2026, 6, 3), "em_andamento", "concluida")], concluida_em=_em(2026, 6, 3))
        _tarefa(s, None, 302, _em(2026, 6, 2), "concluida", ids["ana"], [(_em(2026, 6, 4), "em_andamento", "concluida")], concluida_em=_em(2026, 6, 4))  # pessoal
        _tarefa(s, None, 303, _em(2026, 6, 2), "a_fazer", ids["ana"])
        s.commit()
    params = {"de": "2026-06-01", "ate": "2026-06-14"}
    # A própria pessoa vê tudo (equipe e pessoais)
    d = cliente.get(f"{URL}/pessoas/{ids['ana']}/desempenho", params=params, headers=h["ana"]).json()
    assert d["escopo"] == "pessoa" and d["equipe_id"] is None and d["equipe_nome"] == "Ana Executora"
    assert d["tarefas_no_periodo"] == 3 and d["resumo"]["concluidas_no_periodo"] == 2 and d["resumo"]["abertas_agora"] == 1
    # A liderança vê só as tarefas da equipe que lidera: a tarefa pessoal da Ana não aparece
    d = cliente.get(f"{URL}/pessoas/{ids['ana']}/desempenho", params=params, headers=h["lia"]).json()
    assert d["tarefas_no_periodo"] == 1 and d["resumo"]["concluidas_no_periodo"] == 1
    # Quem não é a pessoa nem a lidera não vê; pessoa inexistente: 404; período inválido: 400
    assert cliente.get(f"{URL}/pessoas/{ids['lia']}/desempenho", params=params, headers=h["ana"]).status_code == 403
    assert cliente.get(f"{URL}/pessoas/999999/desempenho", headers=h["ana"]).status_code == 404
    assert cliente.get(f"{URL}/pessoas/{ids['ana']}/desempenho", params={"de": "2026-06-10", "ate": "2026-06-01"}, headers=h["ana"]).status_code == 400
