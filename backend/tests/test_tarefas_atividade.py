# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a visão "O que aconteceu" (atividade diária da equipe) das Tarefas.
"""`GET /api/tarefas/equipes/{id}/atividade`: dia > tarefa > o que houve, só para a liderança."""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.tarefas import EventoTarefa, Tarefa
from tests.test_tarefas import URL, _mover, _nova, equipe  # noqa: F401  (fixture da equipe)


def _atividade(cliente, h, equipe_id, **params):
    return cliente.get(f"{URL}/equipes/{equipe_id}/atividade", params=params, headers=h)


def test_so_a_lideranca_ve_e_nao_vaza_para_outras_equipes(cliente, equipe):
    ids, h, equipe_id = equipe
    assert _atividade(cliente, h["lia"], equipe_id).status_code == 200
    # Membro comum da equipe: a equipe existe para ele, mas a visão é da liderança
    assert _atividade(cliente, h["ana"], equipe_id).status_code == 403
    # Quem é de fora nem descobre que a equipe existe
    assert _atividade(cliente, h["caio"], equipe_id).status_code == 404
    assert _atividade(cliente, h["lia"], str(uuid.uuid4())).status_code == 404


def test_agrupa_por_dia_e_tarefa_com_resumo_e_conta_comentarios_e_entregas(cliente, equipe):
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"], titulo="Revisar edital")
    outra = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"], titulo="Preparar ata")
    n = t["numero"]
    assert _mover(cliente, h["ana"], n, "iniciar").status_code == 200
    assert cliente.post(f"{URL}/{n}/comentarios", data={"texto": "Conferi as cláusulas."}, headers=h["ana"]).status_code == 201
    assert _mover(cliente, h["ana"], n, "entregar", "Segue o link do Forms: https://forms.exemplo/abc").status_code == 200

    r = _atividade(cliente, h["lia"], equipe_id)
    assert r.status_code == 200, r.text
    dias = r.json()["dias"]
    assert len(dias) == 1
    hoje = dias[0]
    # As duas tarefas criadas hoje aparecem; a que teve mais movimento (ou a mais recente) vem primeiro
    titulos = [x["titulo"] for x in hoje["tarefas"]]
    assert set(titulos) == {"Revisar edital", "Preparar ata"}
    assert hoje["resumo"]["tarefas"] == 2 and hoje["resumo"]["entregues"] == 1 and hoje["resumo"]["comentarios"] == 1
    revisar = next(x for x in hoje["tarefas"] if x["numero"] == n)
    tipos = [i["tipo"] for i in revisar["itens"]]
    assert "entregue" in tipos and "comentario" in tipos
    assert [i["hora"] for i in revisar["itens"]] == sorted(i["hora"] for i in revisar["itens"])  # cronológico
    assert outra["numero"] in {x["numero"] for x in hoje["tarefas"]}


def test_filtros_de_pessoa_tipo_e_busca(cliente, equipe):
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"], titulo="Revisar edital")
    _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"], titulo="Preparar ata")
    cliente.post(f"{URL}/{t['numero']}/comentarios", data={"texto": "Oi"}, headers=h["ana"])
    so_comentarios = _atividade(cliente, h["lia"], equipe_id, tipos="comentarios").json()["dias"][0]
    assert [x["numero"] for x in so_comentarios["tarefas"]] == [t["numero"]]
    assert all(i["tipo"] == "comentario" for x in so_comentarios["tarefas"] for i in x["itens"])
    da_ana = _atividade(cliente, h["lia"], equipe_id, pessoa_id=ids["ana"]).json()["dias"][0]
    assert [x["numero"] for x in da_ana["tarefas"]] == [t["numero"]]
    achado = _atividade(cliente, h["lia"], equipe_id, busca="ata").json()["dias"][0]
    assert [x["titulo"] for x in achado["tarefas"]] == ["Preparar ata"]
    assert _atividade(cliente, h["lia"], equipe_id, tipos="inventado").status_code == 400


def test_checklist_vira_uma_linha_removidos_ficam_fora_e_o_dia_e_o_de_sao_paulo(cliente, equipe):
    ids, h, equipe_id = equipe
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    n = t["numero"]
    for texto in ("Conferir anexo", "Revisar minuta"):
        cliente.post(f"{URL}/{n}/checklist", json={"acao": "incluir", "texto": texto}, headers=h["ana"])
    comentario = cliente.post(f"{URL}/{n}/comentarios", data={"texto": "Segredo"}, headers=h["ana"]).json()
    with FabricaSessao() as s:
        # Um evento às 23h30 de Brasília (02h30 UTC do dia seguinte) de ontem; outro removido
        tarefa = s.scalar(select(Tarefa).where(Tarefa.numero == n))
        ontem = datetime.now(timezone.utc).astimezone().date() - timedelta(days=1)
        s.add(EventoTarefa(id=uuid.uuid4(), tarefa_id=tarefa.id, tipo="comentario", autor_id=ids["ana"], autor_nome="Ana", titulo="Comentário", texto="Tarde da noite",
                           criado_em=datetime(ontem.year, ontem.month, ontem.day, 23, 30, tzinfo=timezone(timedelta(hours=-3))).astimezone(timezone.utc)))
        evento = s.get(EventoTarefa, uuid.UUID(comentario["id"]))
        evento.removido_em = datetime.now(timezone.utc)
        s.commit()
    dias = _atividade(cliente, h["lia"], equipe_id).json()["dias"]
    hoje = next(d for d in dias if any(x["numero"] == n and any(i["tipo"] == "checklist" for i in x["itens"]) for x in d["tarefas"]))
    itens = next(x for x in hoje["tarefas"] if x["numero"] == n)["itens"]
    lista = [i for i in itens if i["tipo"] == "checklist"]
    assert len(lista) == 1 and lista[0]["agrupados"] == 2 and "2 alterações" in lista[0]["titulo"]
    assert all(i["texto"] != "Segredo" for i in itens)  # removido
    # O comentário das 23h30 de ontem em Brasília conta no dia de ontem, não no de hoje
    ontem_dia = next(d for d in dias if any(i["texto"] == "Tarde da noite" for x in d["tarefas"] for i in x["itens"]))
    assert ontem_dia["data"] == (datetime.now(timezone.utc).astimezone().date() - timedelta(days=1)).isoformat() or ontem_dia["data"] != hoje["data"]


def test_limite_de_31_dias_e_periodo_invertido(cliente, equipe):
    ids, h, equipe_id = equipe
    assert _atividade(cliente, h["lia"], equipe_id, de="2026-01-01", ate="2026-03-01").status_code == 400
    assert _atividade(cliente, h["lia"], equipe_id, de="2026-02-10", ate="2026-02-01").status_code == 400
    assert _atividade(cliente, h["lia"], equipe_id, de="2026-02-01", ate="2026-03-03").status_code == 200


def test_subtarefa_aparece_ligada_a_mae(cliente, equipe):
    ids, h, equipe_id = equipe
    mae = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"], titulo="Mãe")
    sub = cliente.post(f"{URL}/{mae['numero']}/subtarefas", json={"titulo": "Filha"}, headers=h["lia"]).json()
    cliente.post(f"{URL}/{sub['numero']}/comentarios", data={"texto": "Na subtarefa"}, headers=h["lia"])
    hoje = _atividade(cliente, h["lia"], equipe_id).json()["dias"][0]
    filha = next(x for x in hoje["tarefas"] if x["numero"] == sub["numero"])
    assert filha["tarefa_pai_numero"] == mae["numero"]
