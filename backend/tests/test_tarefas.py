# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o Módulo Tarefas: pipeline com validação, permissões, prazo, transferência, linha do tempo, avisos e carga.
"""Módulo Tarefas (`/api/tarefas`)."""

import json
import uuid
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
    # Atalho dos testes: `responsavel_id` = responsável principal; `outros_ids` = demais responsáveis
    if "responsavel_id" in extra:
        extra["responsaveis_ids"] = [extra.pop("responsavel_id"), *extra.pop("outros_ids", [])]
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
    r = cliente.post(URL, json={"titulo": "X", "prazo": _prazo(3), "equipe_id": equipe_id, "responsaveis_ids": [ids["caio"]]}, headers=h["ana"])
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
    assert cliente.put(f"{URL}/{n}", json={"titulo": "Novo", "prioridade": "alta", "responsaveis_ids": [ids["ana"]], "versao": 1}, headers=h["ana"]).status_code == 409
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
    # Só o dono configura; membros e liderança criam marcadores na hora (quem é de fora da equipe, não)
    corpo = {"nome": "Contratos", "lideres_ids": [ids["lia"]], "membros_ids": [ids["ana"]]}
    assert cliente.put(f"{URL}/equipes/{equipe_id}", json=corpo, headers=h["ana"]).status_code == 403
    assert cliente.post(f"{URL}/equipes/{equipe_id}/marcadores", json={"nome": "Urgente"}, headers=h["caio"]).status_code == 403
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
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"], outros_ids=[ids["beto"]])
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
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["beto"], outros_ids=[ids["ana"]])
    n = t["numero"]
    cliente.post(f"{URL}/{n}/comentarios", data={"texto": "Primeiro"}, headers=h["ana"])
    arquivo = ("nota.txt", BytesIO(b"conteudo"), "text/plain")
    cliente.post(f"{URL}/{n}/comentarios", data={"texto": "Com anexo"}, files=[("arquivos", arquivo)], headers=h["beto"])
    item = next(i for i in cliente.get(URL, params={"escopo": "equipe", "equipe_id": equipe_id}, headers=h["lia"]).json()["itens"] if i["numero"] == n)
    assert [p["nome"] for p in item["responsaveis"]] == ["Beto Membro", "Ana Executora"]
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
    assert titulos["Já feita"]["status"] == "concluida"
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


def _atrasar(numero: int, dias: int) -> None:
    """Põe o prazo da tarefa `dias` dias no passado (direto no banco; a API não aceita prazo vencido)."""
    with FabricaSessao() as s:
        tarefa = s.scalar(select(servico_tarefas.Tarefa).where(servico_tarefas.Tarefa.numero == numero))
        tarefa.prazo = datetime.now(timezone.utc) - timedelta(days=dias, hours=1)
        s.commit()


def _rodar_lembretes() -> dict[str, int]:
    with FabricaSessao() as s:
        return servico_tarefas.lembrar(s, date.today())


def test_escalonamento_gera_um_memorial_por_lider_por_dia(cliente, admin, equipe):
    ids, h, equipe_id = equipe
    chefe = criar_usuario("chefe", nome_completo="Chefe Geral", email="chefe@sp.gov.br")
    pai = cliente.post(f"{URL}/equipes", json={"nome": "Diretoria", "lideres_ids": [chefe], "membros_ids": []}, headers=admin).json()["id"]
    with FabricaSessao() as s:
        s.get(servico_tarefas.EquipeTarefas, uuid.UUID(equipe_id)).equipe_pai_id = uuid.UUID(pai)
        s.commit()
    a = _nova(cliente, h["lia"], equipe_id, titulo="Revisar edital", responsavel_id=ids["ana"])
    b = _nova(cliente, h["lia"], equipe_id, titulo="Enviar | relatório", responsavel_id=ids["beto"])
    # Atrasadas há 1 dia (2 no pior caso do fuso): só o nível 1 (Lia); UM aviso com as duas tarefas, não um por tarefa
    _atrasar(a["numero"], 1)
    _atrasar(b["numero"], 1)
    contagem = _rodar_lembretes()
    assert contagem["tarefas_escalonadas"] == 2 and contagem["escalonadas"] >= 1
    with FabricaSessao() as s:
        memorial = s.scalars(select(Mensagem).where(Mensagem.chave.like(f"tarefa-escalonada:{ids['lia']}:%"))).all()
        assert len(memorial) == 1 and memorial[0].enviar_email and memorial[0].assunto == "Tarefas atrasadas das suas equipes: 2"
        corpo = memorial[0].corpo
    # Tabela: número, título (sem quebrar a tabela), responsável, atraso e link
    assert "| Nº | Título | Responsável | Atraso | Em aberto | Link |" in corpo and "Enviar / relatório" in corpo
    assert f"| #{a['numero']} | Revisar edital | Ana Executora |" in corpo and f"/tarefas/{b['numero']} |" in corpo
    # Rodar de novo no mesmo dia não repete o aviso
    _rodar_lembretes()
    with FabricaSessao() as s:
        assert len(s.scalars(select(Mensagem).where(Mensagem.chave.like(f"tarefa-escalonada:{ids['lia']}:%"))).all()) == 1
    # Atrasada há 3+ dias: o chefe (equipe acima) também recebe o seu memorial; Lia continua recebendo o dela
    _atrasar(a["numero"], 5)
    _rodar_lembretes()
    with FabricaSessao() as s:
        do_chefe = s.scalars(select(Mensagem).where(Mensagem.chave.like(f"tarefa-escalonada:{chefe}:%"))).all()
        assert len(do_chefe) == 1 and "Revisar edital" in do_chefe[0].corpo and "Enviar" not in do_chefe[0].corpo
    # Linha do tempo: um evento por nível e prazo, sem repetir a cada dia
    eventos = [e for e in cliente.get(f"{URL}/{a['numero']}/linha-do-tempo", headers=h["lia"]).json()["itens"] if e["tipo"] == "escalonada"]
    assert len(eventos) == 3 and any("nível 2" in e["titulo"] for e in eventos)  # nível 1 (prazo antigo), nível 1 e 2 (prazo novo)


def test_escalonamento_de_tarefa_pessoal_vai_ao_criador_e_ignora_o_que_nao_esta_atrasado(cliente, equipe):
    ids, h, _ = equipe
    pessoal = cliente.post(URL, json={"titulo": "Minha tarefa", "descricao": "x", "prazo": _prazo(10)}, headers=h["ana"]).json()
    no_prazo = cliente.post(URL, json={"titulo": "No prazo", "descricao": "x", "prazo": _prazo(10)}, headers=h["ana"]).json()
    _atrasar(pessoal["numero"], 1)
    assert _rodar_lembretes()["tarefas_escalonadas"] == 1
    with FabricaSessao() as s:
        do_criador = s.scalars(select(Mensagem).where(Mensagem.chave.like(f"tarefa-escalonada:{ids['ana']}:%"))).all()
        assert len(do_criador) == 1 and "Minha tarefa" in do_criador[0].corpo and "No prazo" not in do_criador[0].corpo


def test_varios_responsaveis_na_criacao_e_na_edicao(cliente, equipe):
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsaveis_ids=[ids["ana"], ids["beto"]])
    assert t["responsavel"]["id"] == ids["ana"] and [p["id"] for p in t["responsaveis"]] == [ids["ana"], ids["beto"]]
    # Os dois veem a tarefa e executam (iniciam) com os mesmos poderes
    for quem in ("ana", "beto"):
        assert "iniciar" in cliente.get(f"{URL}/{t['numero']}", headers=h[quem]).json()["acoes"]
    # Edição: sem responsáveis é recusada; trocar a lista mantém o principal se ele ficar
    corpo = {"titulo": t["titulo"], "prioridade": "normal", "versao": t["versao"]}
    assert cliente.put(f"{URL}/{t['numero']}", json={**corpo, "responsaveis_ids": []}, headers=h["lia"]).status_code == 422
    r = cliente.put(f"{URL}/{t['numero']}", json={**corpo, "responsaveis_ids": [ids["beto"], ids["ana"]]}, headers=h["lia"])
    assert r.status_code == 200 and r.json()["responsavel"]["id"] == ids["ana"]
    # Se o principal sai, o primeiro da lista assume
    r = cliente.put(f"{URL}/{t['numero']}", json={**corpo, "responsaveis_ids": [ids["beto"]], "versao": r.json()["versao"]}, headers=h["lia"])
    assert r.status_code == 200 and r.json()["responsavel"]["id"] == ids["beto"] and len(r.json()["responsaveis"]) == 1
    # Sem responsáveis informados, fica com quem cadastra
    sem = _nova(cliente, h["lia"], equipe_id)
    assert sem["responsavel"]["id"] == ids["lia"]


def test_editar_equipe_mantendo_lideres_e_membros_nao_viola_a_unicidade(cliente, equipe):
    ids, h, equipe_id = equipe
    corpo = {"nome": "Contratos renomeada", "lideres_ids": [ids["lia"]], "membros_ids": [ids["ana"], ids["beto"]]}
    r = cliente.put(f"{URL}/equipes/{equipe_id}", json=corpo, headers=h["lia"])
    assert r.status_code == 200, r.text
    # Troca parcial: sai o Beto, entra o Caio, a liderança e a Ana continuam
    corpo["membros_ids"] = [ids["ana"], ids["caio"]]
    r = cliente.put(f"{URL}/equipes/{equipe_id}", json=corpo, headers=h["lia"])
    assert r.status_code == 200, r.text
    assert sorted(m["id"] for m in r.json()["membros"]) == sorted([ids["ana"], ids["caio"]])


def test_marcadores_estilo_odoo_uso_busca_criacao_e_cor(cliente, equipe):
    ids, h, equipe_id = equipe
    base = f"{URL}/equipes/{equipe_id}/marcadores"
    # Quem é membro cria na hora; a cor sorteia da paleta (1 a 11); nome repetido (sem diferenciar maiúsculas) devolve o mesmo marcador
    criado = cliente.post(base, json={"nome": "Licitação"}, headers=h["ana"])
    assert criado.status_code == 201 and 1 <= criado.json()["cor_indice"] <= 11
    assert cliente.post(base, json={"nome": "  licitação "}, headers=h["beto"]).json()["id"] == criado.json()["id"]
    urgente = cliente.post(base, json={"nome": "Urgente", "cor_indice": 1}, headers=h["ana"]).json()
    assert urgente["cor_indice"] == 1 and urgente["cor"] == "#d76a58"
    jur = cliente.post(base, json={"nome": "Jurídico", "cor": "#c82331"}, headers=h["lia"]).json()  # hexadecimal legado → cor da paleta
    assert jur["cor_indice"] == 1
    # Mais usado primeiro: duas tarefas com "Urgente", uma com "Jurídico"
    for _ in range(2):
        _nova(cliente, h["lia"], equipe_id, marcadores_ids=[urgente["id"]])
    _nova(cliente, h["lia"], equipe_id, marcadores_ids=[jur["id"]])
    lista = cliente.get(base, headers=h["ana"]).json()
    assert [m["nome"] for m in lista] == ["Urgente", "Jurídico", "Licitação"] and [m["usos"] for m in lista] == [2, 1, 0]
    # Busca por trecho, sem maiúsculas nem acentos, e limite
    assert [m["nome"] for m in cliente.get(base, params={"busca": "JURIDI"}, headers=h["ana"]).json()] == ["Jurídico"]
    assert [m["nome"] for m in cliente.get(base, params={"busca": "i"}, headers=h["ana"]).json()] == ["Jurídico", "Licitação"]
    assert len(cliente.get(base, params={"limite": 1}, headers=h["ana"]).json()) == 1
    # Trocar nome e cor: só a liderança; nome repetido dá 409
    assert cliente.put(f"{base}/{urgente['id']}", json={"nome": "Urgente!", "cor_indice": 4}, headers=h["ana"]).status_code == 403
    r = cliente.put(f"{base}/{urgente['id']}", json={"nome": "Urgente!", "cor_indice": 4}, headers=h["lia"])
    assert r.status_code == 200 and r.json()["nome"] == "Urgente!" and r.json()["cor_indice"] == 4
    assert cliente.put(f"{base}/{urgente['id']}", json={"nome": "jurídico"}, headers=h["lia"]).status_code == 409
    assert cliente.put(f"{base}/{urgente['id']}", json={"nome": "X", "cor_indice": 12}, headers=h["lia"]).status_code == 422


def test_paleta_acha_a_cor_mais_proxima():
    from app.services.tarefas import paleta

    assert paleta.indice_mais_proximo("#c82331") == 1 and paleta.indice_mais_proximo("#5364ce") == 8
    assert paleta.indice_mais_proximo("#8e8e8e") == 0 and len(paleta.PALETA) == 12


def test_responder_a_um_comentario_cita_o_original_e_vai_para_o_topo(cliente, equipe):
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    n = t["numero"]
    original = cliente.post(f"{URL}/{n}/comentarios", data={"texto": "Precisamos do parecer jurídico antes de seguir."}, headers=h["ana"]).json()
    cliente.post(f"{URL}/{n}/comentarios", data={"texto": "Outro assunto"}, headers=h["lia"])
    r = cliente.post(f"{URL}/{n}/comentarios", data={"texto": "Já pedi ao jurídico.", "em_resposta_a": original["id"]}, headers=h["lia"])
    assert r.status_code == 201, r.text
    dados = r.json()["dados"]
    assert dados["resposta_a"] == original["id"] and dados["resposta_autor"] == original["autor"] and dados["resposta_texto"].startswith("Precisamos do parecer")
    # A resposta é o item mais novo: vem no topo da linha do tempo
    topo = cliente.get(f"{URL}/{n}/linha-do-tempo", params={"filtro": "comentarios"}, headers=h["lia"]).json()["itens"][0]
    assert topo["texto"] == "Já pedi ao jurídico." and topo["dados"]["resposta_a"] == original["id"]
    # Só se responde a comentário desta tarefa: id inexistente ou de outra tarefa dá 404
    assert cliente.post(f"{URL}/{n}/comentarios", data={"texto": "x", "em_resposta_a": str(uuid.uuid4())}, headers=h["lia"]).status_code == 404
    outra = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    assert cliente.post(f"{URL}/{outra['numero']}/comentarios", data={"texto": "x", "em_resposta_a": original["id"]}, headers=h["lia"]).status_code == 404
