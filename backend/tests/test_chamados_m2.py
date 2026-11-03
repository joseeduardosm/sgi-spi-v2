# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o marco 2 dos Chamados: pendência, "Não resolveu", campos adicionais, em cópia, aprovação, alterações, tarefas e local.
"""Marco 2 dos Chamados (`/api/chamados`). Usa o mesmo cenário de `test_chamados.py` (Suporte TI, solicitante, técnico e outra pessoa)."""

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.auditoria import RegistroAuditoria
from app.models.chamados import Chamado
from app.models.patrimonio import Localizacao
from app.services.chamados import motor_sla
from tests.test_chamados import BASE, _abrir, _preparar, _responder


def _detalhe(cliente, cab, numero):
    return cliente.get(f"{BASE}/{numero}", headers=cab).json()


def _resolver(cliente, cab, numero):
    r = cliente.post(f"{BASE}/{numero}/solucao", data={"dados": json.dumps({"texto": "<p>Feito.</p>"})}, headers=cab)
    assert r.status_code == 201, r.text
    return r.json()


def test_pendente_pausa_o_prazo_e_a_resposta_do_solicitante_retoma(cliente, admin):
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    r = cliente.post(f"{BASE}/{numero}/pendente", json={"motivo": "Aguardando o número de série"}, headers=c["cab"]["tecnico"])
    assert r.status_code == 200 and r.json()["status_base"] == "pendente" and r.json()["solucao"]["pausado"]
    assert cliente.post(f"{BASE}/{numero}/pendente", json={}, headers=c["cab"]["solicitante"]).status_code == 403
    # O solicitante vê "Aguardando você"; ao responder, o atendimento volta
    assert _responder(cliente, c["cab"]["solicitante"], numero, "<p>Série 12345.</p>").status_code == 201
    assert _detalhe(cliente, c["cab"]["tecnico"], numero)["status_base"] == "novo"


def test_retomar_empurra_o_prazo_pelo_tempo_util_parado(cliente, admin):
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    cliente.post(f"{BASE}/{numero}/pendente", json={}, headers=c["cab"]["tecnico"])
    # Simula que ficou pendente de segunda 9h a segunda 11h (2 horas úteis)
    inicio = datetime(2026, 11, 9, 12, tzinfo=UTC)  # 09:00 em São Paulo
    with FabricaSessao() as sessao:
        chamado = sessao.scalar(select(Chamado).where(Chamado.numero == numero))
        prazo_antes = chamado.prazo_ttr.replace(tzinfo=UTC) if chamado.prazo_ttr.tzinfo is None else chamado.prazo_ttr
        chamado.espera_desde = inicio
        sessao.commit()
    faixas = {d: [(datetime.min.time().replace(hour=8), datetime.min.time().replace(hour=18))] for d in range(5)}
    parado = motor_sla.minutos_uteis_entre(inicio, datetime.now(UTC), faixas, set())
    r = cliente.post(f"{BASE}/{numero}/retomar", headers=c["cab"]["tecnico"])
    assert r.status_code == 200 and r.json()["status_base"] == "novo"
    with FabricaSessao() as sessao:
        chamado = sessao.scalar(select(Chamado).where(Chamado.numero == numero))
        assert chamado.espera_minutos_uteis >= parado - 1
        assert chamado.espera_desde is None
        prazo_depois = chamado.prazo_ttr.replace(tzinfo=UTC) if chamado.prazo_ttr.tzinfo is None else chamado.prazo_ttr
        assert prazo_depois >= prazo_antes


def test_nao_resolveu_reabre_no_prazo_e_so_para_quem_pediu(cliente, admin):
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    resolvido = _resolver(cliente, c["cab"]["tecnico"], numero)
    assert resolvido["acoes"]["nao_resolveu"] is False  # o técnico não reabre
    assert _detalhe(cliente, c["cab"]["solicitante"], numero)["acoes"]["nao_resolveu"] is True
    assert cliente.post(f"{BASE}/{numero}/nao-resolveu", json={"motivo": "ok"}, headers=c["cab"]["solicitante"]).status_code == 400
    r = cliente.post(f"{BASE}/{numero}/nao-resolveu", json={"motivo": "Continua sem imprimir"}, headers=c["cab"]["solicitante"])
    assert r.status_code == 200, r.text
    assert r.json()["status_base"] == "em_atendimento" and r.json()["reaberturas"] == 1 and r.json()["solucionado_em"] is None
    # Resolve de novo e o prazo de reabertura vence
    _resolver(cliente, c["cab"]["tecnico"], numero)
    with FabricaSessao() as sessao:
        sessao.scalar(select(Chamado).where(Chamado.numero == numero)).reabrir_ate = datetime.now(UTC) - timedelta(minutes=1)
        sessao.commit()
    r = cliente.post(f"{BASE}/{numero}/nao-resolveu", json={"motivo": "De novo parou"}, headers=c["cab"]["solicitante"])
    assert r.status_code == 409 and r.json()["codigo"] == "prazo_reabertura"


def test_campos_adicionais_condicao_obrigatorio_e_dado_pessoal(cliente, admin):
    c = _preparar(cliente, admin)
    raiz, filha = c["ids"]["raiz"], c["ids"]["categoria"]
    cpf = cliente.post(f"{BASE}/parametros/categorias/{raiz}/campos", json={"rotulo": "CPF", "tipo": "texto", "obrigatorio": True, "dado_pessoal": True},
                       headers=admin).json()["id"]
    tem_obs = cliente.post(f"{BASE}/parametros/categorias/{filha}/campos", json={"rotulo": "Tem observação?", "tipo": "sim_nao"}, headers=admin).json()["id"]
    obs = cliente.post(f"{BASE}/parametros/categorias/{filha}/campos",
                       json={"rotulo": "Observação", "tipo": "texto_longo", "obrigatorio": True, "condicao": {"campo_id": tem_obs, "igual": "Sim"}}, headers=admin)
    assert obs.status_code == 201, obs.text
    # O catálogo da filha traz o campo herdado da raiz primeiro
    filha_cat = next(x for x in cliente.get(f"{BASE}/catalogo", headers=c["cab"]["solicitante"]).json() if x["id"] == filha)
    assert [x["rotulo"] for x in filha_cat["campos"]] == ["CPF", "Tem observação?", "Observação"]
    r = _abrir(cliente, c["cab"]["solicitante"], filha, campos={tem_obs: "Não"})
    assert r.status_code == 400 and r.json()["codigo"] == "campo_obrigatorio"
    r = _abrir(cliente, c["cab"]["solicitante"], filha, campos={cpf: "123.456.789-09", tem_obs: "Sim"})
    assert r.status_code == 400 and "Observação" in r.json()["detalhe"]
    r = _abrir(cliente, c["cab"]["solicitante"], filha, campos={cpf: "123.456.789-09", tem_obs: "Não"})
    assert r.status_code == 201, r.text
    numero = r.json()["numero"]
    # Quem não atende vê mascarado; quem atende vê o valor e pede o completo pela rota auditada
    campo_cpf = next(x for x in r.json()["campos"] if x["rotulo"] == "CPF")
    assert campo_cpf["mascarado"] and "123" not in campo_cpf["valor"]
    do_tecnico = next(x for x in _detalhe(cliente, c["cab"]["tecnico"], numero)["campos"] if x["rotulo"] == "CPF")
    assert do_tecnico["mascarado"] and do_tecnico["pode_revelar"] and not campo_cpf["pode_revelar"]
    assert cliente.get(f"{BASE}/{numero}/dados-pessoais/{cpf}", headers=c["cab"]["solicitante"]).status_code == 403
    assert cliente.get(f"{BASE}/{numero}/dados-pessoais/{cpf}", headers=c["cab"]["tecnico"]).json() == {"valor": "123.456.789-09"}
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(RegistroAuditoria).where(RegistroAuditoria.acao == "chamados.dado_pessoal")) is not None
    # Campo respondido não sai: desative
    assert cliente.delete(f"{BASE}/parametros/categorias/{raiz}/campos/{cpf}", headers=admin).status_code == 409


def test_em_copia_ve_o_chamado_e_aparece_em_meus(cliente, admin):
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    assert cliente.get(f"{BASE}/{numero}", headers=c["cab"]["outro"]).status_code == 404
    r = cliente.post(f"{BASE}/{numero}/em-copia", json={"usuario_id": c["ids"]["outro"]}, headers=c["cab"]["solicitante"])
    assert r.status_code == 201 and [x["usuario_id"] for x in r.json()["em_copia"]] == [c["ids"]["outro"]]
    assert cliente.get(f"{BASE}/{numero}", headers=c["cab"]["outro"]).status_code == 200
    assert numero in [x["numero"] for x in cliente.get(f"{BASE}/meus", headers=c["cab"]["outro"]).json()["itens"]]
    ator = r.json()["em_copia"][0]["id"]
    r = cliente.delete(f"{BASE}/{numero}/em-copia/{ator}", headers=c["cab"]["outro"])
    # Saiu da própria cópia: deixa de ver o chamado e a resposta vem vazia
    assert r.status_code == 200 and r.json() is None


def test_aprovacao_por_pessoa_e_volta_ao_atendimento(cliente, admin):
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    r = cliente.post(f"{BASE}/{numero}/aprovacoes", json={"alvo_usuario_id": c["ids"]["outro"], "pedido": "Aprova a compra do toner?"}, headers=c["cab"]["tecnico"])
    assert r.status_code == 201 and r.json()["status_base"] == "em_aprovacao"
    minhas = cliente.get(f"{BASE}/aprovacoes/minhas", headers=c["cab"]["outro"]).json()
    assert [x["chamado_numero"] for x in minhas] == [numero]
    # O aprovador vê o chamado; não aprovar exige motivo
    assert cliente.get(f"{BASE}/{numero}", headers=c["cab"]["outro"]).status_code == 200
    assert cliente.post(f"{BASE}/aprovacoes/{minhas[0]['id']}/responder", json={"aprovar": False}, headers=c["cab"]["outro"]).status_code == 400
    assert cliente.post(f"{BASE}/aprovacoes/{minhas[0]['id']}/responder", json={"aprovar": True}, headers=c["cab"]["tecnico"]).status_code == 404
    r = cliente.post(f"{BASE}/aprovacoes/{minhas[0]['id']}/responder", json={"aprovar": True, "resposta": "Pode comprar"}, headers=c["cab"]["outro"])
    assert r.status_code == 200 and r.json()["status_base"] == "novo" and r.json()["validacoes"][0]["status"] == "aprovada"
    assert cliente.get(f"{BASE}/aprovacoes/minhas", headers=c["cab"]["outro"]).json() == []


def test_alterar_prioridade_responsavel_e_setor(cliente, admin):
    c = _preparar(cliente, admin)
    chamado = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()
    numero, versao = chamado["numero"], chamado["versao"]
    r = cliente.patch(f"{BASE}/{numero}", json={"versao": versao, "prioridade": "urgente"}, headers=c["cab"]["tecnico"])
    assert r.status_code == 400 and r.json()["codigo"] == "motivo_obrigatorio"
    r = cliente.patch(f"{BASE}/{numero}", json={"versao": versao, "prioridade": "urgente", "motivo_prioridade": "Diretoria parada"}, headers=c["cab"]["tecnico"])
    assert r.status_code == 200 and r.json()["prioridade"] == "urgente" and r.json()["prioridade_origem"] == "responsavel"
    versao = r.json()["versao"]
    assert cliente.patch(f"{BASE}/{numero}", json={"versao": versao - 1, "prioridade": "baixa", "motivo_prioridade": "x" * 6}, headers=c["cab"]["tecnico"]).status_code == 409
    # Responsável precisa ser do setor responsável
    r = cliente.patch(f"{BASE}/{numero}", json={"versao": versao, "responsavel_id": c["ids"]["outro"]}, headers=c["cab"]["tecnico"])
    assert r.status_code == 400 and r.json()["codigo"] == "responsavel_invalido"
    r = cliente.patch(f"{BASE}/{numero}", json={"versao": versao, "responsavel_id": c["ids"]["tecnico"]}, headers=c["cab"]["tecnico"])
    assert r.status_code == 200 and r.json()["status_base"] == "em_atendimento"
    # Trocar o setor tira o responsável que não é do setor novo
    r = cliente.patch(f"{BASE}/{numero}", json={"versao": r.json()["versao"], "setor_id": c["ids"]["setor_rh"]}, headers=c["cab"]["tecnico"])
    # O técnico não é do setor novo: deixa de ver o chamado (resposta vazia); o administrador vê o setor novo e sem responsável
    assert r.status_code == 200 and r.json() is None
    visto = cliente.get(f"{BASE}/{numero}", headers=admin).json()
    assert visto["setor_nome"] == "Coordenadoria de Pessoas" and visto["responsavel_id"] is None
    assert [x["nome"] for x in cliente.get(f"{BASE}/{numero}/responsaveis", headers=admin).json()] != []


def test_tarefas_privadas_nao_aparecem_para_o_solicitante(cliente, admin):
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    r = cliente.post(f"{BASE}/{numero}/tarefas", json={"texto": "Pedir toner ao fornecedor", "responsavel_id": c["ids"]["tecnico"]}, headers=c["cab"]["tecnico"])
    assert r.status_code == 201 and len(r.json()["tarefas"]) == 1
    tarefa = r.json()["tarefas"][0]["id"]
    assert cliente.patch(f"{BASE}/{numero}/tarefas/{tarefa}", json={"feita": True}, headers=c["cab"]["tecnico"]).json()["tarefas"][0]["estado"] == "feita"
    assert _detalhe(cliente, c["cab"]["solicitante"], numero)["tarefas"] == []
    assert cliente.post(f"{BASE}/{numero}/tarefas", json={"texto": "Eu mesma faço"}, headers=c["cab"]["solicitante"]).status_code == 403


def test_relacionado_so_entre_os_proprios_e_local_sugerido_pelo_patrimonio(cliente, admin):
    c = _preparar(cliente, admin)
    meu = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()
    de_outro = _abrir(cliente, c["cab"]["outro"], c["ids"]["categoria"]).json()
    with FabricaSessao() as sessao:
        sala = Localizacao(id=uuid.uuid4(), tipo="sala", nome="05A03", codigo="05A03", andar=5, lado="A", ativo=True, responsavel_id=c["ids"]["solicitante"])
        sessao.add(sala)
        sessao.commit()
        sala_id = str(sala.id)
    contexto = cliente.get(f"{BASE}/abertura/contexto", headers=c["cab"]["solicitante"]).json()
    assert contexto["local_sugerido"]["id"] == sala_id and "05A03" in contexto["local_sugerido"]["rotulo"]
    assert [x["numero"] for x in contexto["relacionaveis"]] == [meu["numero"]]
    r = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], relacionado_id=de_outro["id"])
    assert r.status_code == 400 and r.json()["codigo"] == "relacionado_invalido"
    r = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], relacionado_id=meu["id"], localizacao_id=sala_id)
    assert r.status_code == 201 and r.json()["relacionado"]["numero"] == meu["numero"] and "05A03" in r.json()["local"]["rotulo"]
    assert [x["rotulo"] for x in cliente.get(f"{BASE}/locais", params={"busca": "05A"}, headers=c["cab"]["solicitante"]).json()] == [contexto["local_sugerido"]["rotulo"]]
