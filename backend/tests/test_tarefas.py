# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o Módulo Tarefas: pipeline com validação, permissões, prazo, transferência, linha do tempo, avisos e carga.
"""Módulo Tarefas (`/api/tarefas`)."""

import json
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
    concluida = _mover(cliente, h["caio"], t["numero"], "entregar").json()
    assert concluida["status"] == "concluida"
    # A validação foi pulada: a etapa não aparece como alcançada
    assert {e["status"]: e["alcancada"] for e in concluida["etapas"]} == {"a_fazer": True, "em_andamento": True, "em_validacao": False, "concluida": True}


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


def test_criar_tarefa_com_anexos(cliente, equipe):
    """Anexos na criação: ficam no evento "Tarefa criada"; arquivo recusado cancela a criação; limite de 5."""
    ids, h, equipe_id = equipe
    corpo = json.dumps({"titulo": "Com anexos", "descricao": "d", "prazo": _prazo(10), "equipe_id": equipe_id})
    arquivos = [("arquivos", ("edital.pdf", BytesIO(b"%PDF-1.4 teste"), "application/pdf")), ("arquivos", ("notas.txt", BytesIO(b"texto"), "text/plain"))]
    r = cliente.post(f"{URL}/com-anexos", data={"dados": corpo}, files=arquivos, headers=h["ana"])
    assert r.status_code == 201, r.text
    n = r.json()["numero"]
    assert r.json()["anexos"] == 2
    criada = next(e for e in cliente.get(f"{URL}/{n}/linha-do-tempo", headers=h["ana"]).json()["itens"] if e["tipo"] == "criada")
    assert sorted(a["nome"] for a in criada["anexos"]) == ["edital.pdf", "notas.txt"]
    assert cliente.get(f"{URL}/{n}/anexos/{criada['anexos'][0]['id']}", headers=h["ana"]).status_code == 200
    # Arquivo recusado: nenhuma tarefa nova
    falso = [("arquivos", ("planilha.xlsx", BytesIO(b"nao e zip"), "application/octet-stream"))]
    assert cliente.post(f"{URL}/com-anexos", data={"dados": corpo}, files=falso, headers=h["ana"]).status_code == 400
    # Mais de 5 arquivos e dados inválidos
    seis = [("arquivos", (f"a{i}.txt", BytesIO(b"x"), "text/plain")) for i in range(6)]
    assert cliente.post(f"{URL}/com-anexos", data={"dados": corpo}, files=seis, headers=h["ana"]).status_code == 400
    assert cliente.post(f"{URL}/com-anexos", data={"dados": "{}"}, headers=h["ana"]).status_code == 422
    assert sum(1 for t in cliente.get(URL, headers=h["ana"]).json()["itens"] if t["titulo"] == "Com anexos") == 1  # só a primeira criação valeu


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


def test_resumo_traz_envolvidos_e_contagens_do_cartao(cliente, equipe):
    """Cartão do quadro: avatares (responsável primeiro), comentários, anexos e datas para o Gantt."""
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["beto"], participantes_ids=[ids["ana"]])
    n = t["numero"]
    cliente.post(f"{URL}/{n}/comentarios", data={"texto": "Primeiro"}, headers=h["ana"])
    arquivo = ("nota.txt", BytesIO(b"conteudo"), "text/plain")
    cliente.post(f"{URL}/{n}/comentarios", data={"texto": "Com anexo"}, files=[("arquivos", arquivo)], headers=h["beto"])
    item = next(i for i in cliente.get(URL, params={"escopo": "equipe", "equipe_id": equipe_id}, headers=h["lia"]).json()["itens"] if i["numero"] == n)
    assert [p["nome"] for p in item["envolvidos"]] == ["Beto Membro", "Ana Executora"]
    assert (item["comentarios"], item["anexos"]) == (2, 1)
    assert item["criado_em"] and item["iniciada_em"] is None
    _mover(cliente, h["beto"], n, "iniciar")
    detalhe = cliente.get(f"{URL}/{n}", headers=h["beto"]).json()
    assert detalhe["iniciada_em"] is not None and detalhe["comentarios"] == 2


def test_agenda_da_pessoa_mostra_todas_as_tarefas_com_titulo(cliente, equipe):
    """Ao atribuir, qualquer usuário vê a agenda da pessoa (com títulos); `abrivel` indica se pode abrir cada tarefa."""
    ids, h, equipe_id = equipe
    da_equipe = _nova(cliente, h["lia"], equipe_id, titulo="Da equipe", responsavel_id=ids["ana"])
    pessoal = _nova(cliente, h["ana"], None, titulo="Pessoal da Ana")
    concluida = _nova(cliente, h["ana"], None, titulo="Já feita")
    _mover(cliente, h["ana"], concluida["numero"], "iniciar")
    _mover(cliente, h["ana"], concluida["numero"], "entregar")
    # O Caio (de fora da equipe) consulta a agenda da Ana: vê tudo, com título, mas não pode abrir
    r = cliente.get(f"{URL}/pessoas/{ids['ana']}/agenda", headers=h["caio"])
    assert r.status_code == 200, r.text
    agenda = r.json()
    assert agenda["pessoa"]["nome"] == "Ana Executora" and agenda["pessoa"]["a_fazer"] == 2
    titulos = {i["titulo"]: i for i in agenda["itens"]}
    assert set(titulos) == {"Da equipe", "Pessoal da Ana", "Já feita"}
    assert titulos["Da equipe"]["papel"] == "responsavel" and titulos["Já feita"]["status"] == "concluida"
    assert not any(i["abrivel"] for i in agenda["itens"])
    # A Lia (liderança) pode abrir a tarefa da equipe, mas não as pessoais da Ana
    abriveis = {i["titulo"] for i in cliente.get(f"{URL}/pessoas/{ids['ana']}/agenda", headers=h["lia"]).json()["itens"] if i["abrivel"]}
    assert abriveis == {"Da equipe"}
    # Concluída fora do período não entra; período invertido e pessoa inexistente
    antes = cliente.get(f"{URL}/pessoas/{ids['ana']}/agenda", params={"de": "2020-01-01", "ate": "2020-01-31"}, headers=h["caio"]).json()
    assert {i["titulo"] for i in antes["itens"]} == {"Da equipe", "Pessoal da Ana"}
    assert cliente.get(f"{URL}/pessoas/{ids['ana']}/agenda", params={"de": "2026-02-01", "ate": "2026-01-01"}, headers=h["caio"]).status_code == 400
    assert cliente.get(f"{URL}/pessoas/999999/agenda", headers=h["caio"]).status_code == 404
    assert pessoal and da_equipe



def test_tarefa_concluida_nao_altera_prazo_e_a_mensagem_explica(cliente, equipe):
    """Tela desatualizada: ao tentar mudar o prazo de uma tarefa já concluída, a API diz o motivo (e que a liderança pode reabrir)."""
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    n = t["numero"]
    assert _mover(cliente, h["lia"], n, "concluir").status_code == 200
    r = cliente.post(f"{URL}/{n}/prazo", json={"prazo": _prazo(20), "justificativa": "Mais tempo"}, headers=h["ana"])
    assert r.status_code == 403 and r.json()["codigo"] == "tarefa_concluida" and "já foi concluída" in r.json()["detalhe"]
    # Depois de reaberta, o prazo volta a poder mudar
    assert _mover(cliente, h["lia"], n, "reabrir", "Faltou um item").status_code == 200
    assert cliente.post(f"{URL}/{n}/prazo", json={"prazo": _prazo(20), "justificativa": "Mais tempo"}, headers=h["ana"]).status_code == 200
