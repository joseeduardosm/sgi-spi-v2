# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar as subtarefas e as dependências entre tarefas.
"""Subtarefas (`POST /{numero}/subtarefas`) e dependências (`PUT /{numero}/dependencias`)."""

from datetime import datetime, timedelta, timezone

from tests.test_tarefas import URL, _nova, _prazo, equipe  # noqa: F401  (fixture da equipe)


def _mover(cliente, h, numero, acao, **extra):
    return cliente.post(f"{URL}/{numero}/mover", json={"acao": acao, **extra}, headers=h)


def test_subtarefa_herda_da_mae_e_bloqueia_a_conclusao_da_mae(cliente, equipe):
    ids, h, equipe_id = equipe
    marcador = cliente.post(f"{URL}/equipes/{equipe_id}/marcadores", json={"nome": "Urgente"}, headers=h["lia"]).json()
    mae = _nova(cliente, h["lia"], equipe_id, responsaveis_ids=[ids["ana"], ids["beto"]], marcadores_ids=[marcador["id"]])
    r = cliente.post(f"{URL}/{mae['numero']}/subtarefas", json={"titulo": "Levantar dados"}, headers=h["lia"])
    assert r.status_code == 201, r.text
    sub = r.json()
    assert sub["tarefa_pai"]["numero"] == mae["numero"] and sub["equipe"]["id"] == equipe_id and [m["id"] for m in sub["marcadores"]] == [marcador["id"]]
    assert sub["responsavel"]["id"] == ids["ana"] and len(sub["responsaveis"]) == 2 and sub["prazo"] == mae["prazo"]
    assert sub["pode_criar_subtarefa"] is False  # subtarefa não tem subtarefa
    assert cliente.post(f"{URL}/{sub['numero']}/subtarefas", json={"titulo": "Neto"}, headers=h["lia"]).status_code == 400
    # Prazo da subtarefa não passa do da mãe
    depois = (datetime.fromisoformat(mae["prazo"]) + timedelta(days=1)).isoformat()
    assert cliente.post(f"{URL}/{mae['numero']}/subtarefas", json={"titulo": "Tarde", "prazo": depois}, headers=h["lia"]).status_code == 400
    # Quem não edita a mãe não cria
    assert cliente.post(f"{URL}/{mae['numero']}/subtarefas", json={"titulo": "X"}, headers=h["caio"]).status_code in (403, 404)

    detalhe = cliente.get(f"{URL}/{mae['numero']}", headers=h["lia"]).json()
    assert [s["numero"] for s in detalhe["subtarefas"]] == [sub["numero"]] and detalhe["subtarefas_total"] == 1 and detalhe["subtarefas_concluidas"] == 0
    # A mãe não entra em validação nem conclui com subtarefa aberta
    assert _mover(cliente, h["ana"], mae["numero"], "iniciar").status_code == 200
    r = _mover(cliente, h["ana"], mae["numero"], "entregar")
    assert r.status_code == 400 and f"#{sub['numero']}" in r.json()["detalhe"]
    assert _mover(cliente, h["lia"], mae["numero"], "concluir").status_code == 400
    # Concluída a subtarefa, a mãe segue o pipeline
    _mover(cliente, h["ana"], sub["numero"], "iniciar")
    assert _mover(cliente, h["ana"], sub["numero"], "entregar").status_code == 200
    assert _mover(cliente, h["lia"], sub["numero"], "validar").status_code == 200
    assert _mover(cliente, h["ana"], mae["numero"], "entregar").status_code == 200
    lista = cliente.get(URL, params={"escopo": "equipe", "equipe_id": equipe_id}, headers=h["lia"]).json()["itens"]
    por_numero = {i["numero"]: i for i in lista}
    assert por_numero[sub["numero"]]["tarefa_pai_numero"] == mae["numero"] and por_numero[mae["numero"]]["subtarefas_concluidas"] == 1


def test_dependencias_bloqueiam_o_inicio_e_impedem_ciclos(cliente, equipe):
    ids, h, equipe_id = equipe
    a = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    b = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    c = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    base = f"{URL}/{b['numero']}/dependencias"
    r = cliente.put(base, json={"numeros": [a["numero"]]}, headers=h["lia"])
    assert r.status_code == 200 and [x["numero"] for x in r.json()["bloqueada_por"]] == [a["numero"]] and r.json()["bloqueada"] is True
    assert [x["numero"] for x in cliente.get(f"{URL}/{a['numero']}", headers=h["lia"]).json()["bloqueia"]] == [b["numero"]]
    # B só inicia depois de A concluída
    r = _mover(cliente, h["ana"], b["numero"], "iniciar")
    assert r.status_code == 400 and f"#{a['numero']}" in r.json()["detalhe"]
    _mover(cliente, h["ana"], a["numero"], "iniciar")
    assert _mover(cliente, h["lia"], a["numero"], "concluir").status_code == 200
    assert cliente.get(f"{URL}/{b['numero']}", headers=h["lia"]).json()["bloqueada"] is False
    assert _mover(cliente, h["ana"], b["numero"], "iniciar").status_code == 200
    # Regras: a si mesma, ciclo (A depende de B que depende de A), número inexistente
    assert cliente.put(base, json={"numeros": [b["numero"]]}, headers=h["lia"]).status_code == 400
    assert cliente.put(f"{URL}/{c['numero']}/dependencias", json={"numeros": [b["numero"]]}, headers=h["lia"]).status_code == 200
    r = cliente.put(f"{URL}/{b['numero']}/dependencias", json={"numeros": [c["numero"]]}, headers=h["lia"])
    assert r.status_code == 400 and "ciclo" in r.json()["detalhe"]
    assert cliente.put(base, json={"numeros": [9999]}, headers=h["lia"]).status_code == 400
    # Limpar a lista libera a tarefa
    assert cliente.put(f"{URL}/{c['numero']}/dependencias", json={"numeros": []}, headers=h["lia"]).json()["bloqueada_por"] == []


def test_excluir_a_mae_leva_as_subtarefas(cliente, equipe):
    ids, h, equipe_id = equipe
    mae = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    sub = cliente.post(f"{URL}/{mae['numero']}/subtarefas", json={"titulo": "Parte 1"}, headers=h["lia"]).json()
    assert cliente.delete(f"{URL}/{mae['numero']}", headers=h["lia"]).status_code == 204
    assert cliente.get(f"{URL}/{sub['numero']}", headers=h["lia"]).status_code == 404
