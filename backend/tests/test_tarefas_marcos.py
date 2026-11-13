"""
===============================================================================
ARQUIVO: test_tarefas_marcos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar os marcos (metas com data-alvo) das equipes de tarefas e o registro
de status da equipe, incluindo o lembrete semanal de atualização de status.

RESUMO TÉCNICO:
Cria marcos por `/api/tarefas/equipes/{id}/marcos`, liga tarefas com `PUT
/{numero}/marco` e confere a situação calculada (no_prazo, em_risco,
atrasado, atingido), o atingimento automático e manual, a edição e a
exclusão. Também testa `/equipes/{id}/status` e a função
`servico_marcos.lembrar`. O SMTP é simulado por `simular_smtp` e os avisos
são lidos nas tabelas de notificação.

FINALIDADE DE NEGÓCIO:
Protege o acompanhamento de entregas da equipe: a liderança define metas, o
sistema avisa quando o marco é atingido ou está em risco, e lembra toda
segunda-feira quem precisa publicar o status da equipe, sem repetir o
lembrete.

CONTEXTO NO SISTEMA:
Usa `tests/apoio_rh.py` (SMTP falso), `tests/test_tarefas.py` (fixture
`equipe`), os modelos `Notificacao`/`EntregaNotificacao` e o serviço
`app/services/tarefas/servico_marcos.py`.

===============================================================================
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.notificacao import EntregaNotificacao, Notificacao
from app.services.tarefas import servico_marcos
from tests.apoio_rh import simular_smtp
from tests.test_tarefas import URL, _nova, equipe  # noqa: F401  (fixture da equipe)


@pytest.fixture(autouse=True)
def _smtp(monkeypatch):
    """Fixture automática (`autouse=True`): vale para todos os testes do arquivo sem ser pedida.

    `monkeypatch` é a fixture do pytest que troca funções/atributos só durante o teste;
    aqui ela substitui o envio real de e-mail por um SMTP simulado.
    """
    simular_smtp(monkeypatch)


def _avisos(prefixo: str) -> list[int]:
    """Lista os ids de quem recebeu notificações cuja chave começa com `prefixo` (ex.: "tarefa-marco:")."""
    with FabricaSessao() as s:
        return [e.destinatario_id for e in s.scalars(select(EntregaNotificacao).join(Notificacao).where(Notificacao.chave.startswith(prefixo)))]


def _concluir(cliente, h, numero, responsavel="ana"):
    """Leva a tarefa até "Concluída" pelo fluxo normal: iniciar, entregar (executor) e validar (liderança)."""
    cliente.post(f"{URL}/{numero}/mover", json={"acao": "iniciar"}, headers=h[responsavel])
    assert cliente.post(f"{URL}/{numero}/mover", json={"acao": "entregar"}, headers=h[responsavel]).status_code == 200
    assert cliente.post(f"{URL}/{numero}/mover", json={"acao": "validar"}, headers=h["lia"]).status_code == 200


def test_marco_progresso_situacao_e_atingimento(cliente, equipe):
    """Ciclo completo de um marco: criar, ligar tarefas, atingir (automático e manual), reabrir, alterar e excluir."""
    ids, h, equipe_id = equipe
    base = f"{URL}/equipes/{equipe_id}/marcos"
    assert cliente.post(base, json={"nome": "Entrega", "data_alvo": "2026-12-31"}, headers=h["ana"]).status_code == 403  # só a liderança
    m = cliente.post(base, json={"nome": "Entrega 1", "data_alvo": (date.today() + timedelta(days=30)).isoformat()}, headers=h["lia"])
    assert m.status_code == 201 and m.json()["situacao"] == "no_prazo" and m.json()["total"] == 0
    assert cliente.post(base, json={"nome": "entrega 1", "data_alvo": "2026-12-31"}, headers=h["lia"]).status_code == 409
    marco = m.json()
    a = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    b = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    # Ligar tarefas ao marco (da mesma equipe; quem edita)
    assert cliente.put(f"{URL}/{a['numero']}/marco", json={"marco_id": marco["id"]}, headers=h["ana"]).json()["marco_id"] == marco["id"]
    cliente.put(f"{URL}/{b['numero']}/marco", json={"marco_id": marco["id"]}, headers=h["lia"])
    assert cliente.put(f"{URL}/{a['numero']}/marco", json={"marco_id": "00000000-0000-0000-0000-000000000000"}, headers=h["lia"]).status_code == 400
    lista = cliente.get(base, headers=h["beto"]).json()
    assert (lista[0]["total"], lista[0]["concluidas"], lista[0]["situacao"]) == (2, 0, "no_prazo")
    # Concluir as duas atinge o marco e avisa a equipe; reabrir uma tira o atingimento (decisão automática)
    _concluir(cliente, h, a["numero"])
    assert cliente.get(base, headers=h["lia"]).json()[0]["situacao"] == "no_prazo"
    _concluir(cliente, h, b["numero"])
    atingido = cliente.get(base, headers=h["lia"]).json()[0]
    assert atingido["situacao"] == "atingido" and atingido["concluidas"] == 2 and atingido["atingido_em"]
    assert ids["ana"] in _avisos(f"tarefa-marco:{marco['id']}")
    assert cliente.post(f"{URL}/{b['numero']}/mover", json={"acao": "reabrir", "texto": "faltou algo"}, headers=h["lia"]).status_code == 200
    assert cliente.get(base, headers=h["lia"]).json()[0]["situacao"] == "no_prazo"
    # Decisão manual: atingir fixa o estado; reabrir manualmente também
    assert cliente.post(f"{URL}/marcos/{marco['id']}/atingir", headers=h["ana"]).status_code == 403
    assert cliente.post(f"{URL}/marcos/{marco['id']}/atingir", headers=h["lia"]).json()["situacao"] == "atingido"
    _concluir(cliente, h, b["numero"])
    assert cliente.get(base, headers=h["lia"]).json()[0]["situacao"] == "atingido"
    assert cliente.post(f"{URL}/marcos/{marco['id']}/reabrir", headers=h["lia"]).json()["situacao"] == "no_prazo"
    # Alterar e excluir (tarefas ficam, sem marco)
    assert cliente.put(f"{URL}/marcos/{marco['id']}", json={"nome": "Entrega final", "data_alvo": "2026-12-31"}, headers=h["lia"]).json()["nome"] == "Entrega final"
    assert cliente.delete(f"{URL}/marcos/{marco['id']}", headers=h["lia"]).status_code == 204
    assert cliente.get(f"{URL}/{a['numero']}", headers=h["lia"]).json()["marco_id"] is None
    assert cliente.get(base, headers=h["caio"]).status_code == 404


def test_marco_atrasado_e_em_risco(cliente, equipe):
    """Data-alvo vencida = "atrasado"; tarefa ligada com prazo depois da data-alvo = "em_risco"."""
    ids, h, equipe_id = equipe
    base = f"{URL}/equipes/{equipe_id}/marcos"
    atrasado = cliente.post(base, json={"nome": "Já passou", "data_alvo": (date.today() - timedelta(days=2)).isoformat()}, headers=h["lia"]).json()
    risco = cliente.post(base, json={"nome": "Apertado", "data_alvo": (date.today() + timedelta(days=2)).isoformat()}, headers=h["lia"]).json()
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])  # prazo em 10 dias: depois da data-alvo do "Apertado"
    cliente.put(f"{URL}/{t['numero']}/marco", json={"marco_id": risco["id"]}, headers=h["lia"])
    por_nome = {m["nome"]: m for m in cliente.get(base, headers=h["lia"]).json()}
    assert por_nome["Já passou"]["situacao"] == "atrasado" and por_nome["Apertado"]["situacao"] == "em_risco"
    assert atrasado["id"] != risco["id"]


def test_status_da_equipe_e_lembrete_semanal(cliente, equipe):
    """Só a liderança publica o status; a equipe é avisada; o lembrete sai às segundas e uma vez só."""
    ids, h, equipe_id = equipe
    base = f"{URL}/equipes/{equipe_id}/status"
    assert cliente.post(base, json={"situacao": "em_risco", "texto": "Atraso do fornecedor"}, headers=h["ana"]).status_code == 403
    assert cliente.post(base, json={"situacao": "quase"}, headers=h["lia"]).status_code == 422
    r = cliente.post(base, json={"situacao": "em_risco", "texto": "Atraso do fornecedor"}, headers=h["lia"])
    assert r.status_code == 201 and r.json()["situacao"] == "em_risco" and r.json()["autor_nome"] == "Lia Líder"
    assert ids["ana"] in _avisos("tarefa-status-equipe:")
    cliente.post(base, json={"situacao": "no_prazo"}, headers=h["lia"])
    historico = cliente.get(base, headers=h["beto"]).json()
    assert [x["situacao"] for x in historico] == ["no_prazo", "em_risco"]
    assert cliente.get(base, headers=h["caio"]).status_code == 404
    # Desempenho traz o status atual e os marcos
    d = cliente.get(f"{URL}/equipes/{equipe_id}/desempenho", headers=h["lia"]).json()
    assert d["status_atual"]["situacao"] == "no_prazo" and d["marcos"] == []
    # Lembrete: só às segundas, com tarefa aberta e sem atualização há 7 dias
    _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    # Próxima segunda-feira (weekday() == 0) estritamente depois de hoje
    segunda = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
    with FabricaSessao() as s:
        assert servico_marcos.lembrar(s, segunda + timedelta(days=1)) == 0  # terça-feira não lembra
        assert servico_marcos.lembrar(s, segunda) == 0  # atualização recente (menos de 7 dias antes da segunda): não lembra
        assert servico_marcos.lembrar(s, segunda + timedelta(days=14)) == 1  # passaram mais de 7 dias
        assert servico_marcos.lembrar(s, segunda + timedelta(days=14)) == 0  # idempotente
