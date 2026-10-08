# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a Reserva de Espaços (conflito, recorrência, análise dos fiscais, cancelamento, permissões e painel).
"""Reserva de Espaços (`/api/reserva-espacos`)."""

from datetime import date, timedelta

from sqlalchemy import select

from app.core.banco import FabricaSessao, hoje_sao_paulo
from app.models.mensagem import Mensagem
from app.models.reserva_espacos import EventoReservaEspaco
from app.services import servico_reserva_espacos as servico
from tests.conftest import cabecalho, criar_usuario

URL = "/api/reserva-espacos"


def _dia(dias: int = 10) -> str:
    """Dia útil (segunda a sexta) a partir de hoje + `dias`."""
    d = hoje_sao_paulo() + timedelta(days=dias)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.isoformat()


def _corpo(espaco_id: int, dia: str | None = None, ini="09:00", fim="10:00", **extras) -> dict:
    return {"espaco_id": espaco_id, "data": dia or _dia(), "hora_inicio": ini, "hora_fim": fim, "titulo": "Reunião de alinhamento", **extras}


def _preparar(cliente, admin):
    """Espaço, fiscal e solicitante; devolve (espaco_id, cabeçalho do fiscal, cabeçalho do solicitante, ids)."""
    fiscal_id = criar_usuario("fiscal1", nome_completo="Fiscal Um")
    solicitante_id = criar_usuario("pessoa1", nome_completo="Pessoa Um")
    espaco = cliente.post(f"{URL}/espacos", json={"nome": "Sala Rodoanel", "localizacao": "2º andar", "cor": "#3810c6", "capacidade": 10}, headers=admin)
    assert espaco.status_code == 201, espaco.text
    r = cliente.put(f"{URL}/configuracao", json={"hora_abertura": "07:00", "hora_fechamento": "19:00", "fiscais_ids": [fiscal_id]}, headers=admin)
    assert r.status_code == 200, r.text
    return espaco.json()["id"], cabecalho(cliente, "fiscal1"), cabecalho(cliente, "pessoa1"), (fiscal_id, solicitante_id)


def test_exige_login(cliente):
    assert cliente.get(f"{URL}/contexto").status_code == 401


def test_papeis_e_espacos(cliente, admin):
    espaco_id, fiscal, pessoa, _ = _preparar(cliente, admin)
    assert cliente.get(f"{URL}/contexto", headers=fiscal).json()["eh_fiscal"] is True
    assert cliente.get(f"{URL}/contexto", headers=pessoa).json()["eh_fiscal"] is False
    # Solicitante comum não cadastra espaço, não vê fila, painel nem configuração
    assert cliente.post(f"{URL}/espacos", json={"nome": "X"}, headers=pessoa).status_code == 403
    for rota in ("fila", "painel", "configuracao", "reservas", "exportar"):
        assert cliente.get(f"{URL}/{rota}", headers=pessoa).status_code == 403, rota
    # Só o SuperRoot grava a configuração
    assert cliente.put(f"{URL}/configuracao", json={"hora_abertura": "07:00", "hora_fechamento": "19:00"}, headers=fiscal).status_code == 403
    # Nome repetido
    assert cliente.post(f"{URL}/espacos", json={"nome": "sala rodoanel"}, headers=fiscal).status_code == 409
    # Com reservas, excluir apenas inativa
    assert cliente.post(f"{URL}/reservas", json=_corpo(espaco_id), headers=pessoa).status_code == 201
    assert cliente.delete(f"{URL}/espacos/{espaco_id}", headers=fiscal).json() == {"resultado": "inativado"}
    assert cliente.get(f"{URL}/contexto", headers=pessoa).json()["espacos"] == []


def test_solicitar_deferir_e_conflito(cliente, admin):
    espaco_id, fiscal, pessoa, (fiscal_id, _) = _preparar(cliente, admin)
    dia = _dia()
    a = cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, dia, "09:00", "10:00"), headers=pessoa).json()["reservas"][0]
    assert a["status"] == "AGUARDANDO_APROVACAO"
    # Pendente não bloqueia: outra pessoa pode pedir o mesmo horário (com aviso)
    criar_usuario("pessoa2", nome_completo="Pessoa Dois")
    outra = cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, dia, "09:30", "10:30"), headers=cabecalho(cliente, "pessoa2"))
    assert outra.status_code == 201 and outra.json()["avisos"]
    b = outra.json()["reservas"][0]
    # O fiscal recebeu aviso da nova solicitação
    with FabricaSessao() as sessao:
        assert any("Nova solicitação" in m.assunto for m in sessao.scalars(select(Mensagem)))
    r = cliente.post(f"{URL}/reservas/{a['id']}/analise", json={"decisao": "deferir"}, headers=fiscal)
    assert r.status_code == 200 and r.json()[0]["status"] == "DEFERIDA" and r.json()[0]["fiscal_nome"] == "Fiscal Um"
    # Agora o horário está ocupado: nova solicitação e deferimento da outra dão 409; horário colado (fim = início) é permitido
    assert cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, dia, "09:30", "10:30"), headers=pessoa).status_code == 409
    assert cliente.post(f"{URL}/reservas/{b['id']}/analise", json={"decisao": "deferir"}, headers=fiscal).status_code == 409
    assert cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, dia, "10:00", "11:00"), headers=pessoa).status_code == 201
    # Indeferir exige justificativa
    assert cliente.post(f"{URL}/reservas/{b['id']}/analise", json={"decisao": "indeferir"}, headers=fiscal).status_code == 400
    r = cliente.post(f"{URL}/reservas/{b['id']}/analise", json={"decisao": "indeferir", "justificativa": "Sala ocupada"}, headers=fiscal)
    assert r.json()[0]["status"] == "INDEFERIDA"
    # Disponibilidade
    livres = cliente.get(f"{URL}/disponibilidade", params={"data": dia, "hora_inicio": "09:00", "hora_fim": "10:00"}, headers=pessoa).json()
    assert livres == []
    # Agenda: deferida aparece para todos
    agenda = cliente.get(f"{URL}/agenda", params={"inicio": dia, "fim": dia}, headers=cabecalho(cliente, "pessoa2")).json()
    assert [x["id"] for x in agenda if x["status"] == "DEFERIDA"] == [a["id"]]


def test_solicitante_so_ve_e_altera_o_proprio(cliente, admin):
    espaco_id, fiscal, pessoa, _ = _preparar(cliente, admin)
    r = cliente.post(f"{URL}/reservas", json=_corpo(espaco_id), headers=pessoa).json()["reservas"][0]
    criar_usuario("intruso", nome_completo="Intruso")
    intruso = cabecalho(cliente, "intruso")
    assert cliente.get(f"{URL}/reservas/{r['id']}", headers=intruso).status_code == 403
    assert cliente.put(f"{URL}/reservas/{r['id']}", json={k: r[k] for k in ("espaco_id", "data", "hora_inicio", "hora_fim", "titulo")}, headers=intruso).status_code == 403
    assert cliente.post(f"{URL}/reservas/{r['id']}/cancelamento", json={"motivo": "x"}, headers=intruso).status_code == 403
    # O dono edita enquanto aguarda; depois de deferida, não
    edicao = {"espaco_id": espaco_id, "data": r["data"], "hora_inicio": "11:00", "hora_fim": "12:00", "titulo": "Novo título"}
    assert cliente.put(f"{URL}/reservas/{r['id']}", json=edicao, headers=pessoa).json()["titulo"] == "Novo título"
    cliente.post(f"{URL}/reservas/{r['id']}/analise", json={"decisao": "deferir"}, headers=fiscal)
    assert cliente.put(f"{URL}/reservas/{r['id']}", json=edicao, headers=pessoa).status_code == 409
    detalhe = cliente.get(f"{URL}/reservas/{r['id']}", headers=pessoa).json()
    assert [e["tipo"] for e in detalhe["eventos"]] == ["CRIACAO", "EDICAO", "DEFERIMENTO"]
    assert cliente.get(f"{URL}/minhas", headers=pessoa).json()[0]["id"] == r["id"]
    assert cliente.get(f"{URL}/minhas", headers=intruso).json() == []


def test_recorrencia_e_acoes_em_serie(cliente, admin):
    espaco_id, fiscal, pessoa, _ = _preparar(cliente, admin)
    inicio = hoje_sao_paulo() + timedelta(days=5)
    corpo = _corpo(espaco_id, inicio.isoformat(), recorrencia="semanal", recorrencia_ate=(inicio + timedelta(weeks=3)).isoformat())
    r = cliente.post(f"{URL}/reservas", json=corpo, headers=pessoa)
    assert r.status_code == 201 and len(r.json()["reservas"]) == 4
    primeira = r.json()["reservas"][0]
    assert primeira["ocorrencias_serie"] == 4 and primeira["serie_id"]
    # Sem data final → erro; deferir vale para a série toda
    assert cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, recorrencia="diaria"), headers=pessoa).status_code == 400
    analise = cliente.post(f"{URL}/reservas/{primeira['id']}/analise", json={"decisao": "deferir"}, headers=fiscal).json()
    assert len(analise) == 4 and {x["status"] for x in analise} == {"DEFERIDA"}
    # Cancelar: motivo obrigatório; uma ocorrência; período; série
    assert cliente.post(f"{URL}/reservas/{primeira['id']}/cancelamento", json={"escopo": "ocorrencia", "motivo": " "}, headers=pessoa).status_code == 400
    assert cliente.post(f"{URL}/reservas/{primeira['id']}/cancelamento", json={"escopo": "ocorrencia", "motivo": "Mudança de agenda"}, headers=pessoa).json()[0]["status"] == "CANCELADA"
    segunda = r.json()["reservas"][1]
    em_periodo = cliente.post(f"{URL}/reservas/{segunda['id']}/cancelamento", json={"escopo": "periodo", "motivo": "Férias", "de": segunda["data"], "ate": r.json()["reservas"][2]["data"]}, headers=pessoa)
    assert len(em_periodo.json()) == 2
    resto = cliente.post(f"{URL}/reservas/{r.json()['reservas'][3]['id']}/cancelamento", json={"escopo": "serie", "motivo": "Fim do projeto"}, headers=pessoa)
    assert len(resto.json()) == 1
    # Cancelamento do solicitante avisa os fiscais
    with FabricaSessao() as sessao:
        assert any("Reserva cancelada" in m.assunto for m in sessao.scalars(select(Mensagem)))
        assert sessao.scalar(select(EventoReservaEspaco).where(EventoReservaEspaco.tipo == "CANCELAMENTO")) is not None


def test_mensal_ajusta_fim_de_mes():
    assert servico.datas_da_recorrencia(date(2027, 1, 31), "mensal", date(2027, 4, 30)) == [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]
    assert servico.datas_da_recorrencia(date(2027, 1, 4), "quinzenal", date(2027, 2, 1)) == [date(2027, 1, 4), date(2027, 1, 18), date(2027, 2, 1)]


def test_predefinida_regras_de_horario_e_painel(cliente, admin):
    espaco_id, fiscal, pessoa, (_, solicitante_id) = _preparar(cliente, admin)
    # Só fiscal cria predefinida; ela já nasce deferida e bloqueia o horário
    assert cliente.post(f"{URL}/reservas/predefinida", json=_corpo(espaco_id, responsavel_nome="Alguém"), headers=pessoa).status_code == 403
    assert cliente.post(f"{URL}/reservas/predefinida", json=_corpo(espaco_id), headers=fiscal).status_code == 400  # falta o responsável
    ok = cliente.post(f"{URL}/reservas/predefinida", json=_corpo(espaco_id, responsavel_id=solicitante_id), headers=fiscal)
    assert ok.status_code == 201 and ok.json()["reservas"][0]["status"] == "DEFERIDA" and ok.json()["reservas"][0]["responsavel_nome"] == "Pessoa Um"
    assert cliente.post(f"{URL}/reservas", json=_corpo(espaco_id), headers=pessoa).status_code == 409
    # Fora do horário de funcionamento, horário invertido e data passada
    assert cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, ini="05:00", fim="06:00"), headers=pessoa).status_code == 400
    assert cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, ini="11:00", fim="10:00"), headers=pessoa).status_code == 400
    assert cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, (hoje_sao_paulo() - timedelta(days=1)).isoformat()), headers=pessoa).status_code == 400
    # Duração máxima e capacidade (aviso)
    cliente.put(f"{URL}/configuracao", json={"hora_abertura": "07:00", "hora_fechamento": "19:00", "duracao_maxima_horas": 2, "fiscais_ids": []}, headers=admin)
    assert cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, _dia(20), "09:00", "13:00"), headers=pessoa).status_code == 400
    aviso = cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, _dia(21), participantes=50), headers=pessoa)
    assert aviso.status_code == 201 and "comporta" in aviso.json()["avisos"][0]
    # Painel e exportação (agora só o SuperRoot é fiscal, pois a lista ficou vazia)
    hoje = hoje_sao_paulo()
    painel = cliente.get(f"{URL}/painel", params={"ano": hoje.year, "mes": hoje.month}, headers=admin)
    assert painel.status_code == 200 and painel.json()["espacos_ativos"] == 1 and len(painel.json()["por_mes"]) == 12
    exportacao = cliente.get(f"{URL}/exportar", headers=admin)
    assert exportacao.status_code == 200 and exportacao.content[:2] == b"PK"


def test_lembrete_um_dia_antes_e_fila(cliente, admin):
    espaco_id, fiscal, pessoa, _ = _preparar(cliente, admin)
    amanha = hoje_sao_paulo() + timedelta(days=1)
    r = cliente.post(f"{URL}/reservas/predefinida", json=_corpo(espaco_id, amanha.isoformat(), responsavel_nome="Chefia"), headers=fiscal)
    assert r.status_code == 201
    pendente = cliente.post(f"{URL}/reservas", json=_corpo(espaco_id, _dia(30)), headers=pessoa).json()["reservas"][0]
    fila = cliente.get(f"{URL}/fila", headers=fiscal).json()
    assert [x["id"] for x in fila] == [pendente["id"]]
    with FabricaSessao() as sessao:
        # A predefinida de amanhã não tem usuário a avisar (responsável digitado); o solicitante é o fiscal, que também é avisado
        assert servico.lembrar(sessao, hoje_sao_paulo()) == 1
        assert servico.lembrar(sessao, hoje_sao_paulo()) == 0
