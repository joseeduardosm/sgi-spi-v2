# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar as atividades agendadas, os seguidores e as menções nas tarefas.
"""Atividades agendadas, seguidores e menções."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.mensagem import EntregaMensagem, Mensagem
from app.services.tarefas import servico_atividades
from tests.apoio_rh import simular_smtp
from tests.test_tarefas import URL, _nova, equipe  # noqa: F401  (fixture da equipe)


@pytest.fixture(autouse=True)
def _smtp(monkeypatch):
    simular_smtp(monkeypatch)


def _avisos(prefixo: str) -> list[int]:
    with FabricaSessao() as s:
        return [e.destinatario_id for e in s.scalars(select(EntregaMensagem).join(Mensagem).where(Mensagem.chave.startswith(prefixo)))]


def test_agendar_concluir_e_historico(cliente, equipe):
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    amanha = (date.today() + timedelta(days=1)).isoformat()
    r = cliente.post(f"{URL}/{t['numero']}/atividades", json={"resumo": "Ligar para a empresa", "tipo": "ligar", "prazo": amanha, "responsavel_id": ids["ana"]}, headers=h["lia"])
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["situacao"] == "futura" and a["responsavel"]["id"] == ids["ana"] and a["tarefa_numero"] == t["numero"]
    assert ids["ana"] in _avisos(f"tarefa-atividade:{a['id']}")  # quem foi agendado é avisado
    # Tipo inválido, fora da equipe e quem não participa
    assert cliente.post(f"{URL}/{t['numero']}/atividades", json={"resumo": "X", "tipo": "voar"}, headers=h["lia"]).status_code == 422
    assert cliente.post(f"{URL}/{t['numero']}/atividades", json={"resumo": "X", "responsavel_id": ids["caio"]}, headers=h["ana"]).status_code == 400  # membro não agenda para quem é de fora da equipe
    assert cliente.post(f"{URL}/{t['numero']}/atividades", json={"resumo": "X"}, headers=h["caio"]).status_code in (403, 404)
    # Aparece em "Minhas atividades" da Ana; quem não é dela não conclui; concluir registra o feedback na linha do tempo e avisa quem agendou
    minhas = cliente.get(f"{URL}/atividades", headers=h["ana"]).json()
    assert [m["id"] for m in minhas] == [a["id"]]
    assert cliente.post(f"{URL}/atividades/{a['id']}/concluir", json={}, headers=h["beto"]).status_code == 403
    r = cliente.post(f"{URL}/atividades/{a['id']}/concluir", json={"feedback": "Combinado envio na sexta"}, headers=h["ana"])
    assert r.status_code == 200 and r.json()["situacao"] == "concluida" and r.json()["feedback"] == "Combinado envio na sexta"
    assert ids["lia"] in _avisos(f"tarefa-atividade-feita:{a['id']}")
    assert cliente.post(f"{URL}/atividades/{a['id']}/concluir", json={}, headers=h["ana"]).status_code == 409
    assert cliente.get(f"{URL}/atividades", headers=h["ana"]).json() == []
    assert len(cliente.get(f"{URL}/atividades", params={"concluidas": True}, headers=h["ana"]).json()) == 1
    linha = cliente.get(f"{URL}/{t['numero']}/linha-do-tempo", headers=h["lia"]).json()
    titulos = [e["titulo"] for e in linha["itens"]]
    assert any(x.startswith("Atividade agendada") for x in titulos) and any(x.startswith("Atividade concluída") for x in titulos)
    # Detalhe da tarefa e exclusão
    outra = cliente.post(f"{URL}/{t['numero']}/atividades", json={"resumo": "Revisar minuta", "tipo": "revisar"}, headers=h["ana"]).json()
    assert [x["resumo"] for x in cliente.get(f"{URL}/{t['numero']}/atividades", headers=h["lia"]).json()] == ["Revisar minuta", "Ligar para a empresa"]
    assert cliente.delete(f"{URL}/atividades/{outra['id']}", headers=h["beto"]).status_code == 403
    assert cliente.delete(f"{URL}/atividades/{outra['id']}", headers=h["ana"]).status_code == 204


def test_lembrete_diario_avisa_hoje_e_atrasadas_uma_vez_por_dia(cliente, equipe):
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    hoje = date.today()
    cliente.post(f"{URL}/{t['numero']}/atividades", json={"resumo": "De hoje", "prazo": hoje.isoformat(), "responsavel_id": ids["ana"]}, headers=h["lia"])
    cliente.post(f"{URL}/{t['numero']}/atividades", json={"resumo": "Atrasada", "prazo": (hoje - timedelta(days=2)).isoformat(), "responsavel_id": ids["ana"]}, headers=h["lia"])
    cliente.post(f"{URL}/{t['numero']}/atividades", json={"resumo": "Futura", "prazo": (hoje + timedelta(days=3)).isoformat()}, headers=h["lia"])
    with FabricaSessao() as s:
        assert servico_atividades.lembrar(s, hoje) == {"hoje": 1, "atrasadas": 1}
        assert servico_atividades.lembrar(s, hoje) == {"hoje": 2 - 1, "atrasadas": 1}  # contadas de novo, mas o aviso não se repete (mesma chave)
    avisos = _avisos("tarefa-atividade-lembrete:")
    assert avisos.count(ids["ana"]) == 2 and avisos.count(ids["lia"]) == 1  # a Lia (quem agendou) recebe só o da atrasada


def test_seguidor_recebe_avisos_informativos_e_mencao(cliente, equipe):
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    r = cliente.post(f"{URL}/{t['numero']}/seguir", headers=h["beto"])
    assert r.status_code == 200 and r.json()["seguindo"] is True and [p["id"] for p in r.json()["seguidores"]] == [ids["beto"]]
    ev = cliente.post(f"{URL}/{t['numero']}/comentarios", data={"texto": "Atualização do andamento"}, headers=h["ana"]).json()
    assert ids["beto"] in _avisos(f"tarefa-comentario:{ev['id']}")
    # Menção: avisa só quem foi citado (e não repete o comentário genérico para ele)
    ev2 = cliente.post(f"{URL}/{t['numero']}/comentarios", data={"texto": "@beto pode revisar? e @caio?"}, headers=h["ana"]).json()
    assert _avisos(f"tarefa-mencao:{ev2['id']}") == [ids["beto"]]  # Caio é de fora da equipe: não é avisado
    assert ids["beto"] not in _avisos(f"tarefa-comentario:{ev2['id']}")
    # Deixar de seguir
    r = cliente.delete(f"{URL}/{t['numero']}/seguir", headers=h["beto"])
    assert r.json()["seguindo"] is False and r.json()["seguidores"] == []
