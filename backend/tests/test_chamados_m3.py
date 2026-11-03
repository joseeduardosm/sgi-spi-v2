# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o marco 3 dos Chamados: status e sub-status, Geral, setores de atendimento, recorrentes, prazos estourados e saúde.
"""Marco 3 dos Chamados. Usa o cenário de `test_chamados.py` (Suporte TI com o técnico, a solicitante e outra pessoa)."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.core.banco import FUSO_SAO_PAULO, FabricaSessao
from app.models.chamados import Chamado, ExecucaoChamados, RecorrenteChamados
from app.models.notificacao import EntregaNotificacao, Notificacao
from app.services.chamados import configuracao, tarefas_agendadas
from tests.test_chamados import BASE, _abrir, _preparar


def test_status_com_nome_cor_e_substatus(cliente, admin):
    c = _preparar(cliente, admin)
    r = cliente.put(f"{BASE}/parametros/status/novo", json={"nome": "Na fila", "cor": "atencao"}, headers=admin)
    assert r.status_code == 200 and next(x for x in r.json() if x["status_base"] == "novo") == {"status_base": "novo", "nome": "Na fila", "cor": "atencao"}
    chamado = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()
    assert chamado["status_nome"] == "Na fila" and chamado["status_cor"] == "atencao"
    sub = cliente.post(f"{BASE}/parametros/substatus", json={"status_base": "em_atendimento", "nome": "Aguardando peça", "cor": "alerta"}, headers=admin).json()
    # Sub-status de outro status-base é recusado
    r = cliente.patch(f"{BASE}/{chamado['numero']}", json={"versao": chamado["versao"], "substatus_id": sub["id"]}, headers=c["cab"]["tecnico"])
    assert r.status_code == 400 and r.json()["codigo"] == "substatus_invalido"
    r = cliente.post(f"{BASE}/{chamado['numero']}/assumir", json={"versao": chamado["versao"]}, headers=c["cab"]["tecnico"])
    r = cliente.patch(f"{BASE}/{chamado['numero']}", json={"versao": r.json()["versao"], "substatus_id": sub["id"]}, headers=c["cab"]["tecnico"])
    assert r.status_code == 200 and r.json()["status_nome"] == "Em atendimento › Aguardando peça" and r.json()["status_cor"] == "alerta"
    assert [x["nome"] for x in cliente.get(f"{BASE}/substatus", headers=c["cab"]["tecnico"]).json()] == ["Aguardando peça"]
    assert cliente.put(f"{BASE}/parametros/status/novo", json={"nome": "X", "cor": "info"}, headers=c["cab"]["tecnico"]).status_code == 403


def test_parametros_gerais_e_nivel_do_prazo(cliente, admin):
    _preparar(cliente, admin)
    assert cliente.get(f"{BASE}/parametros/geral", headers=admin).json() == {
        "dias_reabrir": 5, "ponto_facultativo_util": False, "limite_alerta": 50, "limite_atencao": 75, "limite_perigo": 90, "inicio_atendimento": None}
    r = cliente.put(f"{BASE}/parametros/geral", json={"dias_reabrir": 5, "ponto_facultativo_util": True, "limite_alerta": 80, "limite_atencao": 70,
                                                      "limite_perigo": 90}, headers=admin)
    assert r.status_code == 400
    r = cliente.put(f"{BASE}/parametros/geral", json={"dias_reabrir": 3, "ponto_facultativo_util": True, "limite_alerta": 40, "limite_atencao": 60,
                                                      "limite_perigo": 80}, headers=admin)
    assert r.status_code == 200 and r.json()["dias_reabrir"] == 3
    limites = configuracao.Geral(5, False, 50, 75, 90)
    assert [configuracao.nivel_do_prazo(p, False, False, True, limites) for p in (10, 50, 75, 90)] == ["ok", "alerta", "atencao", "perigo"]
    assert configuracao.nivel_do_prazo(30, False, True, True, limites) == "cumprido"
    assert configuracao.nivel_do_prazo(None, False, False, False, limites) == "sem"


def _vencer(numero: int, *, tto: bool = True, ttr: bool = True) -> None:
    with FabricaSessao() as sessao:
        chamado = sessao.scalar(select(Chamado).where(Chamado.numero == numero))
        passado = datetime.now(UTC) - timedelta(minutes=5)
        if tto:
            chamado.prazo_tto = passado
        if ttr:
            chamado.prazo_ttr = passado
        sessao.commit()


def test_prazo_de_solucao_estourado_vira_urgente_e_avisa_por_email(cliente, admin):
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    pendente = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], titulo="Pausado").json()["numero"]
    cliente.post(f"{BASE}/{pendente}/pendente", json={}, headers=c["cab"]["tecnico"])
    _vencer(numero)
    _vencer(pendente, tto=False)
    with FabricaSessao() as sessao:
        assert tarefas_agendadas.verificar_prazos(sessao) == (1, 1)
        sessao.commit()
        # Rodar de novo não marca outra vez
        assert tarefas_agendadas.verificar_prazos(sessao) == (0, 0)
    detalhe = cliente.get(f"{BASE}/{numero}", headers=c["cab"]["tecnico"]).json()
    assert detalhe["prioridade"] == "urgente" and detalhe["prioridade_origem"] == "sla" and detalhe["solucao"]["estourado"]
    assert detalhe["solucao"]["nivel"] == "perigo"
    assert any("urgente (automático)" in i["texto"] for i in detalhe["linha_do_tempo"])
    # O pendente não estoura (o relógio está parado)
    assert cliente.get(f"{BASE}/{pendente}", headers=c["cab"]["tecnico"]).json()["prioridade"] != "urgente"
    with FabricaSessao() as sessao:
        entrega = sessao.scalar(select(EntregaNotificacao).join(Notificacao).where(Notificacao.chave.like("chamados:%:sla:ttr:0"),
                                                                                 EntregaNotificacao.destinatario_id == c["ids"]["tecnico"]))
        assert entrega is not None and entrega.canal_email


def test_recorrente_gera_um_chamado_por_ocorrencia_e_pula_fim_de_semana(cliente, admin):
    c = _preparar(cliente, admin)
    agora = datetime.now(UTC)
    corpo = {"nome": "Validar backups", "categoria_id": c["ids"]["categoria"], "titulo": "Validar os backups do dia", "descricao": "<p>Conferir o PBS.</p>",
             "periodicidade_quantidade": 1, "periodicidade_unidade": "dia", "antecedencia_min": 0, "so_dias_uteis": False,
             "proxima_em": (agora - timedelta(minutes=1)).isoformat()}
    r = cliente.post(f"{BASE}/parametros/recorrentes", json=corpo, headers=admin)
    assert r.status_code == 201, r.text
    with FabricaSessao() as sessao:
        assert tarefas_agendadas.gerar_recorrentes(sessao) == 1
        sessao.commit()
        assert tarefas_agendadas.gerar_recorrentes(sessao) == 0
        gerado = sessao.scalar(select(Chamado).where(Chamado.recorrente_id.is_not(None)))
        assert gerado.titulo == "Validar os backups do dia" and gerado.setor_nome == "Suporte TI"
        recorrente = sessao.scalar(select(RecorrenteChamados))
        proxima = recorrente.proxima_em if recorrente.proxima_em.tzinfo else recorrente.proxima_em.replace(tzinfo=UTC)
        assert proxima > agora
    # Sexta 8h, só em dia útil: a seguinte é segunda 8h (e não sábado)
    sexta = datetime(2026, 11, 6, 8, tzinfo=FUSO_SAO_PAULO)
    item = RecorrenteChamados(proxima_em=sexta, periodicidade_quantidade=1, periodicidade_unidade="dia", so_dias_uteis=True)
    assert configuracao.proxima_ocorrencia(item, sexta, set()) == datetime(2026, 11, 9, 8, tzinfo=FUSO_SAO_PAULO)
    assert configuracao.proxima_ocorrencia(item, sexta, {date(2026, 11, 9)}) == datetime(2026, 11, 10, 8, tzinfo=FUSO_SAO_PAULO)
    # Excluir o recorrente mantém o chamado gerado
    assert cliente.delete(f"{BASE}/parametros/recorrentes/{r.json()['id']}", headers=admin).status_code == 204
    assert cliente.get(f"{BASE}/{gerado.numero}", headers=admin).status_code == 200


def test_saude_e_vigia_avisam_pelo_sino(cliente, admin):
    _preparar(cliente, admin)
    s = cliente.get(f"{BASE}/saude", headers=admin).json()
    assert any("nunca rodaram" in p for p in s["problemas"])
    assert tarefas_agendadas.executar(FabricaSessao, "minuto", tarefas_agendadas.rodar_minuto)
    s = cliente.get(f"{BASE}/saude", headers=admin).json()
    assert not any("tarefas automáticas" in p for p in s["problemas"]) and s["tarefas"][0]["ultimo_estado"] == "ok"
    # Rodada que ficou "rodando" há muito tempo: o vigia encerra e avisa quem administra (o root é SuperRoot)
    with FabricaSessao() as sessao:
        sessao.add(ExecucaoChamados(tarefa="minuto", iniciada_em=datetime.now(UTC) - timedelta(hours=1)))
        sessao.query(ExecucaoChamados).filter(ExecucaoChamados.estado == "ok").update({"terminada_em": datetime.now(UTC) - timedelta(hours=1)})
        sessao.commit()
    assert tarefas_agendadas.executar(FabricaSessao, "vigia", tarefas_agendadas.vigiar)
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(ExecucaoChamados).where(ExecucaoChamados.erro.like("Interrompida%"))) is not None
        assert sessao.scalar(select(Notificacao).where(Notificacao.chave.like("chamados:saude:%"))) is not None


def test_setor_que_ve_todos_enxerga_chamados_de_outros_setores(cliente, admin):
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    # Muda o chamado para o setor de RH: o técnico (Suporte TI) deixa de ver
    cliente.patch(f"{BASE}/{numero}", json={"versao": cliente.get(f"{BASE}/{numero}", headers=admin).json()["versao"], "setor_id": c["ids"]["setor_rh"]},
                  headers=admin)
    assert cliente.get(f"{BASE}/{numero}", headers=c["cab"]["tecnico"]).status_code == 404
    r = cliente.put(f"{BASE}/parametros/setores-atendimento/{c['ids']['setor_ti']}", json={"ve_todos": True}, headers=admin)
    assert r.status_code == 200 and r.json()["ve_todos"]
    assert cliente.get(f"{BASE}/{numero}", headers=c["cab"]["tecnico"]).status_code == 200


def test_resumo_diario_vai_so_para_o_lider_com_chamado_aberto_e_uma_vez_por_dia(cliente, admin):
    from app.models.setor import Setor
    c = _preparar(cliente, admin)
    _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"])
    with FabricaSessao() as sessao:
        sessao.get(Setor, c["ids"]["setor_ti"]).lider_id = c["ids"]["tecnico"]
        sessao.get(Setor, c["ids"]["setor_rh"]).lider_id = c["ids"]["outro"]  # setor sem chamado aberto: não recebe
        sessao.commit()
    segunda_8h = datetime(2026, 11, 9, 8, tzinfo=FUSO_SAO_PAULO)
    with FabricaSessao() as sessao:
        # Antes das 7h e no fim de semana, nada
        assert tarefas_agendadas.resumo_diario_lideres(sessao, datetime(2026, 11, 9, 6, tzinfo=FUSO_SAO_PAULO)) == 0
        assert tarefas_agendadas.resumo_diario_lideres(sessao, datetime(2026, 11, 8, 9, tzinfo=FUSO_SAO_PAULO)) == 0
        assert tarefas_agendadas.resumo_diario_lideres(sessao, segunda_8h) == 1
        sessao.commit()
        # A mesma rodada no mesmo dia não manda de novo
        assert tarefas_agendadas.resumo_diario_lideres(sessao, segunda_8h + timedelta(hours=2)) == 0
    with FabricaSessao() as sessao:
        entrega = sessao.scalar(select(EntregaNotificacao).join(Notificacao).where(Notificacao.chave.like("chamados:resumo-lider:%")))
        assert entrega.destinatario_id == c["ids"]["tecnico"] and entrega.canal_email
        assert "Impressora não imprime" in sessao.get(Notificacao, entrega.notificacao_id).corpo
        assert sessao.scalar(select(func.count()).select_from(EntregaNotificacao).join(Notificacao).where(Notificacao.chave.like("chamados:resumo-lider:%"))) == 1
