# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o Módulo Tarefas: pipeline com validação, permissões, prazo, transferência, linha do tempo, avisos e carga.
"""Módulo Tarefas (`/api/tarefas`)."""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.mensagem import EntregaMensagem, Mensagem
from app.services.tarefas import servico_tarefas
from tests.apoio_rh import simular_smtp
from tests.conftest import cabecalho, criar_usuario

URL = "/api/tarefas"


@pytest.fixture(autouse=True)
def _smtp(monkeypatch):
    simular_smtp(monkeypatch)


@pytest.fixture
def equipe(cliente, admin):
    """Lia lidera a equipe Contratos (dona: Lia); Ana e Beto são membros; Caio é de fora."""
    ids = {login: criar_usuario(login, nome_completo=nome, email=f"{login}@sp.gov.br") for login, nome in (
        ("lia", "Lia Líder"), ("ana", "Ana Executora"), ("beto", "Beto Membro"), ("caio", "Caio Externo"))}
    h = {k: cabecalho(cliente, k) for k in ids}
    r = cliente.post(f"{URL}/equipes", json={"nome": "Contratos", "lideres_ids": [ids["lia"]], "membros_ids": [ids["ana"], ids["beto"]]}, headers=h["lia"])
    assert r.status_code == 201, r.text
    return ids, h, r.json()["id"]


def _prazo(dias: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat()


def _nova(cliente, h, equipe_id, **extra):
    corpo = {"titulo": "Revisar edital", "descricao": "Conferir cláusulas", "prazo": _prazo(10), "equipe_id": equipe_id, **extra}
    r = cliente.post(URL, json=corpo, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _avisos(chave_prefixo: str) -> list[tuple[int, bool]]:
    with FabricaSessao() as s:
        return [(e.destinatario_id, e.encerrada_em is not None) for e in s.scalars(
            select(EntregaMensagem).join(Mensagem).where(Mensagem.chave.startswith(chave_prefixo)))]


def _mover(cliente, h, numero, acao, texto=""):
    return cliente.post(f"{URL}/{numero}/mover", json={"acao": acao, "texto": texto}, headers=h)


def test_pipeline_com_entrega_validacao_e_devolucao(cliente, equipe):
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    n = t["numero"]
    assert t["status"] == "a_fazer" and t["prazo_original"] == t["prazo"]
    # A Ana recebe aviso da atribuição (a Lia, autora, não)
    assert _avisos(f"tarefa-criada:{t['id']}") == [(ids["ana"], False)]
    # Ações da Ana: iniciar; a Lia (liderança) pode concluir direto
    assert "iniciar" in cliente.get(f"{URL}/{n}", headers=h["ana"]).json()["acoes"]
    assert _mover(cliente, h["ana"], n, "validar").status_code == 403
    assert _mover(cliente, h["ana"], n, "iniciar").json()["status"] == "em_andamento"
    r = _mover(cliente, h["ana"], n, "entregar", "Pronto, conferido.")
    assert r.json()["status"] == "em_validacao"
    # A liderança recebe o aviso de validação; a executora não pode validar a própria entrega
    assert _avisos(f"tarefa-validacao:{t['id']}:") == [(ids["lia"], False)]
    assert _mover(cliente, h["ana"], n, "validar").status_code == 403
    # Devolver exige motivo; devolvida volta para em andamento e encerra o aviso de validação
    assert _mover(cliente, h["lia"], n, "devolver").status_code == 400
    r = _mover(cliente, h["lia"], n, "devolver", "Faltou a cláusula 7.")
    assert r.json()["status"] == "em_andamento"
    assert _avisos(f"tarefa-validacao:{t['id']}:") == [(ids["lia"], True)]
    assert [d for d, _ in _avisos(f"tarefa-devolvida:{t['id']}:")] == [ids["ana"]]
    _mover(cliente, h["ana"], n, "entregar")
    r = _mover(cliente, h["lia"], n, "validar")
    detalhe = r.json()
    assert detalhe["status"] == "concluida"
    etapas = {e["status"]: e for e in detalhe["etapas"]}
    assert all(e["alcancada"] for e in etapas.values()) and etapas["concluida"]["por"] == "Lia Líder"
    # Reabrir: só a liderança, com motivo
    assert "reabrir" not in cliente.get(f"{URL}/{n}", headers=h["ana"]).json()["acoes"]
    assert _mover(cliente, h["lia"], n, "reabrir", "Cliente pediu ajuste").json()["status"] == "em_andamento"


def test_tarefa_pessoal_conclui_na_entrega(cliente, equipe):
    ids, h, _ = equipe
    t = _nova(cliente, h["caio"], None)
    _mover(cliente, h["caio"], t["numero"], "iniciar")
    assert _mover(cliente, h["caio"], t["numero"], "entregar").json()["status"] == "concluida"


def test_permissoes_visibilidade_e_atribuicao(cliente, equipe):
    ids, h, equipe_id = equipe
    # Fora da equipe não cadastra nela; membro não atribui a quem é de fora; a liderança pode
    assert cliente.post(URL, json={"titulo": "X", "prazo": _prazo(3), "equipe_id": equipe_id}, headers=h["caio"]).status_code == 403
    r = cliente.post(URL, json={"titulo": "X", "prazo": _prazo(3), "equipe_id": equipe_id, "responsavel_id": ids["caio"]}, headers=h["ana"])
    assert r.status_code == 400 and "membros da equipe" in r.json()["detalhe"]
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["caio"])
    # Quem não tem relação com a tarefa recebe 404 (não revela que existe)
    outra = _nova(cliente, h["ana"], None)
    assert cliente.get(f"{URL}/{outra['numero']}", headers=h["beto"]).status_code == 404
    # Membro da equipe vê as tarefas da equipe; a lista "minhas" do Beto não traz a tarefa do Caio
    assert cliente.get(f"{URL}/{t['numero']}", headers=h["beto"]).status_code == 200
    lista = cliente.get(URL, params={"escopo": "equipe", "equipe_id": equipe_id}, headers=h["beto"]).json()
    assert t["numero"] in [i["numero"] for i in lista["itens"]] and not lista["contexto"]["lider"]
    assert t["numero"] not in [i["numero"] for i in cliente.get(URL, headers=h["beto"]).json()["itens"]]
    # Visão da pessoa: a liderança vê; outro membro não
    assert cliente.get(URL, params={"escopo": "pessoa", "login": "ana"}, headers=h["lia"]).status_code == 200
    assert cliente.get(URL, params={"escopo": "pessoa", "login": "ana"}, headers=h["caio"]).status_code == 403


def test_prazo_transferencia_comentario_e_linha_do_tempo(cliente, equipe):
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    n = t["numero"]
    # Prazo: justificativa obrigatória; prorrogações contadas; prazo original preservado
    assert cliente.post(f"{URL}/{n}/prazo", json={"prazo": _prazo(20), "justificativa": " "}, headers=h["ana"]).status_code == 400
    r = cliente.post(f"{URL}/{n}/prazo", json={"prazo": _prazo(20), "justificativa": "Aguardando parecer"}, headers=h["ana"])
    assert r.status_code == 200 and r.json()["prorrogacoes"] == 1 and r.json()["prazo_original"] == t["prazo_original"]
    # Quem alterou não recebe o próprio aviso
    assert ids["ana"] not in [d for d, _ in _avisos(f"tarefa-prazo:{t['id']}")]
    # Conflito de versão
    assert cliente.put(f"{URL}/{n}", json={"titulo": "Novo", "prioridade": "alta", "versao": 1}, headers=h["ana"]).status_code == 409
    # Transferência: membro só para membro; justificativa na linha do tempo
    assert cliente.post(f"{URL}/{n}/transferir", json={"para_id": ids["caio"], "justificativa": "x"}, headers=h["ana"]).status_code == 400
    r = cliente.post(f"{URL}/{n}/transferir", json={"para_id": ids["beto"], "justificativa": "Férias da Ana"}, headers=h["ana"])
    assert r.status_code == 200 and r.json()["responsavel"]["id"] == ids["beto"]
    # Comentário com anexo (formato validado pelo conteúdo)
    arquivos = [("arquivos", ("nota.pdf", BytesIO(b"%PDF-1.4 teste"), "application/pdf"))]
    r = cliente.post(f"{URL}/{n}/comentarios", data={"texto": "Segue a nota."}, files=arquivos, headers=h["beto"])
    assert r.status_code == 201, r.text
    anexo = r.json()["anexos"][0]
    assert cliente.get(f"{URL}/{n}/anexos/{anexo['id']}", headers=h["lia"]).status_code == 200
    falso = [("arquivos", ("planilha.xlsx", BytesIO(b"nao e zip"), "application/octet-stream"))]
    assert cliente.post(f"{URL}/{n}/comentarios", data={"texto": ""}, files=falso, headers=h["beto"]).status_code == 400
    # Linha do tempo: filtros e paginação
    tudo = cliente.get(f"{URL}/{n}/linha-do-tempo", headers=h["lia"]).json()
    tipos = [e["tipo"] for e in tudo["itens"]]
    assert tipos[0] == "comentario" and {"criada", "prazo", "transferida"} <= set(tipos)
    assert [e["tipo"] for e in cliente.get(f"{URL}/{n}/linha-do-tempo", params={"filtro": "prazos"}, headers=h["lia"]).json()["itens"]] == ["prazo"]
    assert cliente.get(f"{URL}/{n}/linha-do-tempo", params={"filtro": "anexos"}, headers=h["lia"]).json()["total"] == 1
    pagina = cliente.get(f"{URL}/{n}/linha-do-tempo", params={"limite": 2}, headers=h["lia"]).json()
    assert pagina["tem_mais"] and len(pagina["itens"]) == 2
    # Remoção de item só pelo SuperRoot
    evento = tudo["itens"][0]["id"]
    assert cliente.post(f"{URL}/{n}/eventos/{evento}/remover", json={"motivo": "x"}, headers=h["lia"]).status_code == 403


def test_carga_indicadores_e_lembretes(cliente, equipe):
    ids, h, equipe_id = equipe
    _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"], prioridade="critica", prazo=_prazo(-1))  # atrasada: 8 × 4
    _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"], prioridade="normal", prazo=_prazo(20))   # 3 × 1
    lista = cliente.get(URL, headers=h["ana"]).json()
    assert lista["indicadores"]["carga"] == 35 and lista["indicadores"]["atrasadas"] == 1 and lista["indicadores"]["faixa"] == "Ocupação moderada"
    pessoas = cliente.get(f"{URL}/pessoas", params={"equipe_id": equipe_id}, headers=h["lia"]).json()
    assert pessoas[0]["login"] == "ana" and pessoas[0]["carga"] == 35
    # Lembretes diários: atrasada → envolvidos; validação parada → liderança em janela
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["beto"])
    _mover(cliente, h["beto"], t["numero"], "iniciar")
    _mover(cliente, h["beto"], t["numero"], "entregar")
    with FabricaSessao() as s:
        tarefa = s.scalar(select(servico_tarefas.Tarefa).where(servico_tarefas.Tarefa.numero == t["numero"]))
        tarefa.entregue_em = datetime.now(timezone.utc) - timedelta(days=3)
        s.commit()
        contagem = servico_tarefas.lembrar(s, date.today())
    assert contagem["atrasadas"] == 1 and contagem["validacao_parada"] == 1
    with FabricaSessao() as s:
        janela = s.scalar(select(Mensagem).where(Mensagem.chave.startswith(f"tarefa-validacao-parada:{t['id']}:")))
        assert janela.abrir_em_janela


def test_equipes_marcadores_e_ordem(cliente, equipe):
    ids, h, equipe_id = equipe
    # Só o dono configura; só a liderança cria marcadores
    corpo = {"nome": "Contratos", "lideres_ids": [ids["lia"]], "membros_ids": [ids["ana"]]}
    assert cliente.put(f"{URL}/equipes/{equipe_id}", json=corpo, headers=h["ana"]).status_code == 403
    assert cliente.post(f"{URL}/equipes/{equipe_id}/marcadores", json={"nome": "Urgente"}, headers=h["ana"]).status_code == 403
    m = cliente.post(f"{URL}/equipes/{equipe_id}/marcadores", json={"nome": "Urgente", "cor": "#c82331"}, headers=h["lia"]).json()
    t = _nova(cliente, h["lia"], equipe_id, marcadores_ids=[m["id"]])
    filtrada = cliente.get(URL, params={"escopo": "equipe", "equipe_id": equipe_id, "marcador_id": m["id"]}, headers=h["lia"]).json()
    assert [i["numero"] for i in filtrada["itens"]] == [t["numero"]]
    # Equipe com tarefa aberta não é excluída
    assert cliente.delete(f"{URL}/equipes/{equipe_id}", headers=h["lia"]).status_code == 400
    # Ordem manual
    t2 = _nova(cliente, h["lia"], equipe_id)
    assert cliente.post(f"{URL}/ordem", json={"numeros": [t2["numero"], t["numero"]]}, headers=h["lia"]).status_code == 204
    itens = cliente.get(URL, params={"escopo": "equipe", "equipe_id": equipe_id}, headers=h["lia"]).json()["itens"]
    assert [i["numero"] for i in itens][:2] == [t2["numero"], t["numero"]]
    # Checklist
    r = cliente.post(f"{URL}/{t['numero']}/checklist", json={"acao": "incluir", "texto": "Conferir anexo"}, headers=h["lia"]).json()
    item = r["checklist"][0]["id"]
    r = cliente.post(f"{URL}/{t['numero']}/checklist", json={"acao": "marcar", "item_id": item}, headers=h["lia"]).json()
    assert r["checklist_feitos"] == 1 and r["checklist_total"] == 1


def test_relatorio_xlsx_e_pdf(cliente, equipe):
    import io

    from openpyxl import load_workbook

    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"], participantes_ids=[ids["beto"]])
    params = {"escopo": "equipe", "equipe_id": equipe_id}
    r = cliente.get(f"{URL}/relatorio", params={**params, "formato": "xlsx"}, headers=h["lia"])
    assert r.status_code == 200 and "tarefas-" in r.headers["content-disposition"]
    livro = load_workbook(io.BytesIO(r.content))
    assert livro.sheetnames == ["Tarefas", "Por pessoa"]
    valores = [c for linha in livro["Tarefas"].iter_rows(values_only=True) for c in linha]
    assert t["numero"] in valores and t["titulo"] in valores
    pessoas = [linha[0] for linha in livro["Por pessoa"].iter_rows(values_only=True)]
    assert any("Ana" in str(p) for p in pessoas) and any("Beto" in str(p) for p in pessoas)
    r = cliente.get(f"{URL}/relatorio", params={**params, "formato": "pdf"}, headers=h["lia"])
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    # Mesmas permissões da lista; período invertido é recusado
    assert cliente.get(f"{URL}/relatorio", params=params, headers=h["caio"]).status_code in (403, 404)
    assert cliente.get(f"{URL}/relatorio", params={**params, "de": "2026-10-10", "ate": "2026-10-01"}, headers=h["lia"]).status_code == 400
    # Período antes da criação: a tarefa fica de fora
    r = cliente.get(f"{URL}/relatorio", params={**params, "formato": "xlsx", "ate": "2020-01-01"}, headers=h["lia"])
    valores = [c for linha in load_workbook(io.BytesIO(r.content))["Tarefas"].iter_rows(values_only=True) for c in linha]
    assert t["titulo"] not in valores


def test_pessoas_da_equipe_com_contagem_na_equipe(cliente, equipe):
    ids, h, equipe_id = equipe
    _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    _nova(cliente, h["ana"], None)  # pessoal: conta na carga, não na equipe
    lista = {p["login"]: p for p in cliente.get(f"{URL}/pessoas", params={"equipe_id": equipe_id}, headers=h["lia"]).json()}
    assert lista["ana"]["a_fazer"] == 2 and lista["ana"]["na_equipe"]["a_fazer"] == 1
    assert lista["beto"]["na_equipe"] == {"a_fazer": 0, "em_andamento": 0, "em_validacao": 0, "concluidas": 0, "atrasadas": 0}
    assert all(p["na_equipe"] is None for p in cliente.get(f"{URL}/pessoas", params={"busca": "a"}, headers=h["lia"]).json())
