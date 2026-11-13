"""
===============================================================================
ARQUIVO: test_rede.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar o plano de face da rede (/api/rede): acesso, modelos, cadastro em
cadeia, portas, lados do patch panel, ligações, caminho, topologia, VLANs,
racks, pontos, indicadores e as cargas automáticas desativadas.

RESUMO TÉCNICO:
O cenário (_cenario) monta a cadeia mínima pela API: SW-CORE (core primário)
→ SW-DIST (distribuição) → SW-5A (acesso), mais o patch panel PP-5A, as VLANs
10 e 20 e dois usuários (analista edita, leitor só vê). Cada teste parte
dele e confere as regras pelas respostas da API.

FINALIDADE DE NEGÓCIO:
Garante as regras decididas para a Rede: cadastro de cima para baixo, porta
sem nada ligado em branco, descrição gerada pelo sistema, fundo e frente no
patch panel e nenhum equipamento sem cabo para quem fica acima dele.

CONTEXTO NO SISTEMA:
Rotas em app/api/routes/rede.py; regras em app/services/rede/servico.py.

===============================================================================
"""
import uuid
from itertools import count

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.rede import EquipamentoRede
from app.services.rede import servico
from tests.conftest import cabecalho, criar_usuario
from tests.test_chamados import BASE as CHAMADOS, _abrir, _preparar

BASE = "/api/rede"
# IPs de gerência diferentes para cada equipamento criado nos testes
_IPS = count(10)


def _recurso(cliente, admin) -> int:
    r = cliente.post("/api/acl/recursos", json={"nome": "Rede", "slug": "rede"}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _lig(numero: int, destino: str, lado: str | None = None, config: dict | None = None, config_destino: dict | None = None) -> dict:
    """Cabo do cadastro: esta porta (número lógico) no destino (id da porta; lado se for patch panel)."""
    return {"porta_numero": numero, "destino_porta_id": destino, "destino_lado": lado, "config": config, "config_destino": config_destino}


def _novo(cliente, admin, nome: str, modelo: str, funcao: str | None = None, tipo: str = "switch", ligacao: dict | None = None):
    corpo = {"nome": nome, "tipo": tipo, "modelo_face_id": modelo, "funcao": funcao, "ligacao": ligacao}
    if tipo != "patch_panel":
        corpo["ip_gerencia"] = f"10.23.9.{next(_IPS) % 250 + 1}"
    return cliente.post(f"{BASE}/equipamentos", json=corpo, headers=admin)


def _cenario(cliente, admin) -> dict:
    """Modelo 2×4 + 2 SFP e patch panel de 8; SW-CORE → SW-DIST → SW-5A em cadeia; PP-5A; VLANs 10 e 20; analista (editar) e leitor (ver)."""
    ids = {"analista": criar_usuario("analista"), "leitor": criar_usuario("leitor")}
    recurso = _recurso(cliente, admin)
    for nivel, quem in (("MODIFICACAO", "analista"), ("LEITURA", "leitor")):
        r = cliente.post("/api/acl/regras", json={"recurso_id": recurso, "nivel": nivel, "usuarios_ids": [ids[quem]], "setores_ids": []}, headers=admin)
        assert r.status_code == 201, r.text
    modelo = cliente.post(f"{BASE}/modelos", json={"nome": "Switch 8+2", "linhas": 2, "colunas": 4, "numeracao": "coluna",
                                                   "portas_extras": [{"numero": 9, "rotulo": "SFP 1", "tipo": "fibra"}, {"numero": 10, "rotulo": "SFP 2", "tipo": "fibra"}]},
                          headers=admin)
    assert modelo.status_code == 201, modelo.text
    painel = cliente.post(f"{BASE}/modelos", json={"nome": "Patch 8", "linhas": 1, "colunas": 8, "numeracao": "linha"}, headers=admin).json()
    v10 = cliente.post(f"{BASE}/vlans", json={"numero": 10, "nome": "Dados"}, headers=admin).json()
    v20 = cliente.post(f"{BASE}/vlans", json={"numero": 20, "nome": "Voz"}, headers=admin).json()
    trunk = {"modo": "trunk", "vlan_nativa_id": v10["id"], "vlans_tag": [v20["id"]], "velocidade_mbps": 10000, "status": "up"}
    m = modelo.json()["id"]
    core = _novo(cliente, admin, "SW-CORE", m, "core_primario")
    assert core.status_code == 201, core.text
    dist = _novo(cliente, admin, "SW-DIST", m, "distribuicao", ligacao=_lig(9, core.json()["portas"][0]["id"], config=trunk, config_destino=trunk))
    assert dist.status_code == 201, dist.text
    switch = _novo(cliente, admin, "SW-5A", m, "acesso", ligacao=_lig(9, dist.json()["portas"][0]["id"], config=trunk, config_destino=trunk))
    assert switch.status_code == 201, switch.text
    patch = _novo(cliente, admin, "PP-5A", painel["id"], tipo="patch_panel").json()
    cab = {k: cabecalho(cliente, k) for k in ("analista", "leitor")}
    return {"ids": ids, "cab": cab, "core": core.json(), "dist": dist.json(), "switch": switch.json(), "patch": patch, "v10": v10, "v20": v20,
            "modelo": modelo.json(), "painel": painel, "trunk": trunk}


def _porta(cliente, cab, porta_id: str) -> dict:
    return cliente.get(f"{BASE}/portas/{porta_id}", headers=cab).json()


# ---------------------------------------------------------------------------------------------
# Acesso, modelos e face
# ---------------------------------------------------------------------------------------------

def test_modulo_fechado_ate_haver_regras(cliente, admin):
    criar_usuario("curioso")
    cab = cabecalho(cliente, "curioso")
    assert cliente.get(f"{BASE}/contexto", headers=cab).json() == {"ver": False, "editar": False, "administrar": False}
    assert cliente.get(f"{BASE}/equipamentos", headers=cab).status_code == 403
    assert cliente.get(f"{BASE}/contexto", headers=admin).json() == {"ver": True, "editar": True, "administrar": True}


def test_face_gerada_pelo_modelo_e_portas_nascem_desligadas(cliente, admin):
    """As portas vêm do modelo, todas desligadas e "Desligado", menos a do cabo do cadastro (ligada, descrita e configurada)."""
    c = _cenario(cliente, admin)
    sw = c["switch"]
    assert [p["numero_logico"] for p in sw["portas"]] == list(range(1, 11)) and sw["portas"][8]["nome"] == "SFP 1"
    assert sw["posicoes"]["1"] == [1, 1] and sw["posicoes"]["2"] == [2, 1] and sw["posicoes"]["3"] == [1, 2] and "9" not in sw["posicoes"]
    assert c["patch"]["posicoes"]["8"] == [1, 8]
    livres = [p for p in sw["portas"] if p["numero_logico"] != 9]
    assert all((p["status"], p["descricao"], p["conexao"]) == ("down", "Desligado", None) for p in livres)
    subida = sw["portas"][8]
    assert (subida["status"], subida["descricao"], subida["modo"], subida["vlan_nativa"], subida["vlans_tag"]) == ("up", "SW-DIST · 1", "trunk", 10, [20])
    # A porta do outro lado também ficou ligada, descrita e configurada
    do_dist = _porta(cliente, admin, c["dist"]["portas"][0]["id"])
    assert (do_dist["status"], do_dist["descricao"], do_dist["modo"], do_dist["velocidade_mbps"]) == ("up", "SW-5A · SFP 1", "trunk", 10000)
    lista = cliente.get(f"{BASE}/equipamentos", headers=c["cab"]["leitor"]).json()
    assert {e["nome"]: e["portas_total"] for e in lista} == {"PP-5A": 8, "SW-5A": 10, "SW-DIST": 10, "SW-CORE": 10}
    r = cliente.put(f"{BASE}/modelos/{c['modelo']['id']}", json={"nome": "Switch 8+2", "linhas": 2, "colunas": 4, "portas_extras": [{"numero": 8}]}, headers=admin)
    assert r.status_code == 400
    assert cliente.delete(f"{BASE}/modelos/{c['modelo']['id']}", headers=admin).json()["codigo"] == "em_uso"
    assert cliente.post(f"{BASE}/modelos", json={"nome": "X", "linhas": 1, "colunas": 1}, headers=c["cab"]["analista"]).status_code == 403


# ---------------------------------------------------------------------------------------------
# Cadastro em cadeia
# ---------------------------------------------------------------------------------------------

def test_cadastro_em_cadeia_de_cima_para_baixo(cliente, admin):
    """Sem core não entra distribuição; sem distribuição não entra acesso; sem acesso não entra AP; cada um liga em quem pode ficar acima."""
    modelo = cliente.post(f"{BASE}/modelos", json={"nome": "Switch 4", "linhas": 1, "colunas": 4}, headers=admin).json()["id"]
    assert _novo(cliente, admin, "D1", modelo, "distribuicao").json()["codigo"] == "cadeia_incompleta"
    assert _novo(cliente, admin, "C2", modelo, "core_secundario").json()["codigo"] == "cadeia_incompleta"
    core = _novo(cliente, admin, "C1", modelo, "core_primario").json()
    # Distribuição sem dizer onde está ligada: 400
    r = _novo(cliente, admin, "D1", modelo, "distribuicao")
    assert (r.status_code, r.json()["codigo"]) == (400, "sem_ligacao")
    assert _novo(cliente, admin, "A1", modelo, "acesso", ligacao=_lig(1, core["portas"][0]["id"])).json()["codigo"] == "cadeia_incompleta"
    assert _novo(cliente, admin, "AP1", modelo, tipo="access_point", ligacao=_lig(1, core["portas"][0]["id"])).json()["codigo"] == "cadeia_incompleta"
    dist = _novo(cliente, admin, "D1", modelo, "distribuicao", ligacao=_lig(4, core["portas"][0]["id"])).json()
    # Porta ocupada no destino; acesso ligado em outro acesso não serve; acesso direto no core serve
    assert _novo(cliente, admin, "A1", modelo, "acesso", ligacao=_lig(4, core["portas"][0]["id"])).json()["codigo"] == "porta_ocupada"
    acesso = _novo(cliente, admin, "A1", modelo, "acesso", ligacao=_lig(4, dist["portas"][0]["id"])).json()
    r = _novo(cliente, admin, "A2", modelo, "acesso", ligacao=_lig(4, acesso["portas"][0]["id"]))
    assert r.json()["codigo"] == "cadeia_invalida" and "distribuição ou um core" in r.json()["detalhe"]
    assert _novo(cliente, admin, "A2", modelo, "acesso", ligacao=_lig(4, core["portas"][1]["id"])).status_code == 201
    # Distribuição só em core; AP só em acesso (e fica sem função); core secundário só no primário
    assert _novo(cliente, admin, "D2", modelo, "distribuicao", ligacao=_lig(4, dist["portas"][1]["id"])).json()["codigo"] == "cadeia_invalida"
    assert _novo(cliente, admin, "AP1", modelo, tipo="access_point", ligacao=_lig(1, dist["portas"][1]["id"])).json()["codigo"] == "cadeia_invalida"
    ap = _novo(cliente, admin, "AP1", modelo, "acesso", tipo="access_point", ligacao=_lig(1, acesso["portas"][1]["id"]))
    assert ap.status_code == 201 and ap.json()["funcao"] is None
    assert _novo(cliente, admin, "C2", modelo, "core_secundario", ligacao=_lig(4, dist["portas"][2]["id"])).json()["codigo"] == "cadeia_invalida"
    assert _novo(cliente, admin, "C2", modelo, "core_secundario", ligacao=_lig(4, core["portas"][2]["id"])).status_code == 201
    # Patch panel e core primário não pedem ligação
    painel = cliente.post(f"{BASE}/modelos", json={"nome": "PP 4", "linhas": 1, "colunas": 4}, headers=admin).json()["id"]
    assert _novo(cliente, admin, "PP1", painel, tipo="patch_panel").status_code == 201


def test_cadastro_atravessando_o_patch_panel(cliente, admin):
    """O cabo do cadastro pode chegar num lado do patch panel, desde que o outro lado daquela porta leve a quem pode ficar acima."""
    c = _cenario(cliente, admin)
    m, pp, cab = c["modelo"]["id"], c["patch"]["portas"], c["cab"]["analista"]
    # Fundo da porta 1 do patch panel ligado na porta 2 da distribuição
    r = cliente.post(f"{BASE}/portas/{pp[0]['id']}/conexao", json={"lado": "fundo", "porta_id": c["dist"]["portas"][1]["id"]}, headers=cab)
    assert r.status_code == 201, r.text
    assert r.json()["descricao"] == "Terminal Punch Down: SW-DIST · 2" and r.json()["fundo"]["texto"] == "SW-DIST · porta 2" and r.json()["frente"] is None
    # Lado obrigatório no patch panel; lado já ocupado; o outro lado vazio não leva a ninguém
    assert _novo(cliente, admin, "SW-6A", m, "acesso", ligacao=_lig(9, pp[0]["id"])).status_code == 400
    assert _novo(cliente, admin, "SW-6A", m, "acesso", ligacao=_lig(9, pp[0]["id"], "fundo")).json()["codigo"] == "porta_ocupada"
    r = _novo(cliente, admin, "SW-6A", m, "acesso", ligacao=_lig(9, pp[1]["id"], "frente"))
    assert r.status_code == 400 and "não leva a nenhum switch" in r.json()["detalhe"]
    novo = _novo(cliente, admin, "SW-6A", m, "acesso", ligacao=_lig(9, pp[0]["id"], "frente", config=c["trunk"]))
    assert novo.status_code == 201, novo.text
    porta_pp = _porta(cliente, admin, pp[0]["id"])
    assert porta_pp["descricao"] == "Terminal Punch Down: SW-DIST · 2 · Conector RJ45: SW-6A · SFP 1" and porta_pp["status"] == "up"
    assert novo.json()["portas"][8]["descricao"] == "PP-5A · 1 (Conector RJ45)"
    # Uma distribuição não pode chegar por um patch panel que leva a um acesso
    cliente.post(f"{BASE}/portas/{pp[2]['id']}/conexao", json={"lado": "fundo", "porta_id": c["switch"]["portas"][2]["id"]}, headers=cab)
    assert _novo(cliente, admin, "SW-DIST2", m, "distribuicao", ligacao=_lig(9, pp[2]["id"], "frente")).json()["codigo"] == "cadeia_invalida"


def test_modelo_tipo_e_funcao_travados_depois_de_criado(cliente, admin):
    c = _cenario(cliente, admin)
    sw, url = c["switch"], f"{BASE}/equipamentos/{c['switch']['id']}"
    campos = ("nome", "tipo", "modelo_face_id", "bem_id", "localizacao_id", "rack_id", "posicao_u", "ip_gerencia", "numero_serie", "observacao", "ativo", "funcao")
    corpo = {k: sw.get(k) for k in campos}
    outro = cliente.post(f"{BASE}/modelos", json={"nome": "Switch 48", "linhas": 2, "colunas": 24, "numeracao": "coluna"}, headers=admin).json()
    assert cliente.put(url, json={**corpo, "modelo_face_id": outro["id"]}, headers=admin).json()["codigo"] == "modelo_travado"
    assert cliente.put(url, json={**corpo, "tipo": "patch_panel"}, headers=admin).json()["codigo"] == "tipo_travado"
    assert cliente.put(url, json={**corpo, "tipo": "roteador"}, headers=admin).json()["codigo"] == "tipo_travado"
    assert cliente.put(url, json={**corpo, "funcao": "distribuicao"}, headers=admin).json()["codigo"] == "funcao_travada"
    r = cliente.put(url, json={**corpo, "numero_serie": "ABC123"}, headers=admin)
    assert r.status_code == 200 and r.json()["numero_serie"] == "ABC123"


# ---------------------------------------------------------------------------------------------
# Porta: descrição gerada, observação e configuração só com algo ligado
# ---------------------------------------------------------------------------------------------

def test_porta_sem_ligacao_fica_desligada_e_em_branco(cliente, admin):
    c = _cenario(cliente, admin)
    porta, cab = c["switch"]["portas"][1]["id"], c["cab"]["analista"]
    # Sem nada ligado: não liga nem configura; desativada ou desligada guarda só a observação
    r = cliente.put(f"{BASE}/portas/{porta}", json={"modo": "trunk", "status": "up"}, headers=cab)
    assert (r.status_code, r.json()["codigo"]) == (409, "porta_sem_ligacao")
    r = cliente.put(f"{BASE}/portas/{porta}", json={"modo": "trunk", "vlans_tag": [c["v20"]["id"]], "status": "desativada", "observacao": "Reservada"}, headers=cab)
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["modo"], r.json()["vlans_tag"], r.json()["descricao"], r.json()["observacao"]) == \
        ("desativada", "access", [], "Desligado", "Reservada")
    # Ligou: fica ligada, a descrição é a do que está ligado e a configuração passa a valer
    r = cliente.post(f"{BASE}/portas/{porta}/conexao", json={"descricao": "Impressora da recepção"}, headers=cab)
    assert (r.json()["status"], r.json()["descricao"], r.json()["observacao"]) == ("up", "Impressora da recepção", "Reservada")
    r = cliente.put(f"{BASE}/portas/{porta}", json={"modo": "access", "vlan_nativa_id": c["v10"]["id"], "status": "up", "observacao": ""}, headers=cab)
    assert (r.json()["vlan_nativa"], r.json()["observacao"]) == (10, "")
    for status in ("down", "desativada", None):
        assert cliente.put(f"{BASE}/portas/{porta}", json={"modo": "access", "status": status}, headers=cab).json()["codigo"] == "porta_com_equipamento"
    assert cliente.put(f"{BASE}/portas/{porta}", json={"modo": "access", "status": "up"}, headers=c["cab"]["leitor"]).status_code == 403


def test_modos_de_porta_das_marcas(cliente, admin):
    """Hybrid (Huawei/3Com), QinQ, DTP (Cisco) e roteada: o que cada modo aceita, VLAN de voz e IP da interface."""
    c = _cenario(cliente, admin)
    porta, cab = c["switch"]["portas"][0]["id"], c["cab"]["analista"]
    cliente.post(f"{BASE}/portas/{porta}/conexao", json={"descricao": "Servidor"}, headers=cab)
    v10, v20 = c["v10"]["id"], c["v20"]["id"]
    v30 = cliente.post(f"{BASE}/vlans", json={"numero": 30, "nome": "Câmeras"}, headers=admin).json()["id"]
    put = lambda corpo: cliente.put(f"{BASE}/portas/{porta}", json={"status": "up", **corpo}, headers=cab)
    r = put({"modo": "hybrid", "vlan_nativa_id": v10, "vlans_sem_tag": [v30], "vlans_tag": [v20], "vlan_voz_id": v20})
    assert r.status_code == 200, r.text
    assert (r.json()["modo"], r.json()["vlan_nativa"], r.json()["vlans_sem_tag"], r.json()["vlans_tag"], r.json()["vlan_voz"]) == ("hybrid", 10, [30], [20], 20)
    assert put({"modo": "hybrid", "vlans_sem_tag": [v30], "vlans_tag": [v30]}).status_code == 400
    assert put({"modo": "trunk", "vlans_sem_tag": [v30]}).status_code == 400
    assert put({"modo": "dot1q_tunnel", "vlan_nativa_id": v30, "vlans_tag": [v20]}).status_code == 400
    assert put({"modo": "trunk", "vlan_voz_id": v20}).status_code == 400
    assert put({"modo": "access", "vlan_nativa_id": v10, "vlan_voz_id": v20}).json()["vlan_voz"] == 20
    assert put({"modo": "dinamico_desejavel", "vlan_nativa_id": v10, "vlans_tag": [v20]}).json()["vlans_tag"] == [20]
    assert put({"modo": "roteada", "vlan_nativa_id": v10}).status_code == 400
    assert put({"modo": "roteada", "ip_interface": "10.23.0.300/30"}).status_code == 400
    assert put({"modo": "access", "ip_interface": "10.23.0.1/30"}).status_code == 400
    r = put({"modo": "roteada", "ip_interface": "10.23.0.1/30"})
    assert (r.json()["modo"], r.json()["ip_interface"], r.json()["vlans_tag"], r.json()["vlan_nativa"]) == ("roteada", "10.23.0.1/30", [], None)
    assert put({"modo": "qualquer"}).status_code == 422
    put({"modo": "access", "vlan_voz_id": v30})
    assert cliente.delete(f"{BASE}/vlans/{v30}", headers=admin).json()["codigo"] == "em_uso"


# ---------------------------------------------------------------------------------------------
# Ligações: lados do patch panel, desligar e excluir sem quebrar a cadeia
# ---------------------------------------------------------------------------------------------

def test_patch_panel_tem_fundo_e_frente(cliente, admin):
    c = _cenario(cliente, admin)
    pp, sw, cab = c["patch"]["portas"][2]["id"], c["switch"]["portas"][6]["id"], c["cab"]["analista"]
    # Sem lado no patch panel, ou com lado fora dele: 400
    assert cliente.post(f"{BASE}/portas/{pp}/conexao", json={"porta_id": sw}, headers=cab).status_code == 400
    assert cliente.post(f"{BASE}/portas/{sw}/conexao", json={"lado": "fundo", "descricao": "X"}, headers=cab).status_code == 400
    r = cliente.post(f"{BASE}/portas/{pp}/conexao", json={"lado": "frente", "porta_id": sw}, headers=cab)
    assert r.status_code == 201 and r.json()["frente"]["texto"] == "SW-5A · porta 7" and r.json()["descricao"] == "Conector RJ45: SW-5A · 7"
    assert _porta(cliente, cab, sw)["descricao"] == "PP-5A · 3 (Conector RJ45)"
    # O outro lado da mesma porta é outra ligação; o mesmo lado não liga duas vezes
    assert cliente.post(f"{BASE}/portas/{pp}/conexao", json={"lado": "frente", "descricao": "Y"}, headers=cab).json()["codigo"] == "porta_ocupada"
    r = cliente.post(f"{BASE}/portas/{pp}/conexao", json={"lado": "fundo", "descricao": "Tomada 5A-12"}, headers=cab)
    assert r.json()["descricao"] == "Terminal Punch Down: Tomada 5A-12 · Conector RJ45: SW-5A · 7"
    # Desligar um lado: a porta continua ligada pelo outro; desligar o segundo: desligada e em branco
    r = cliente.delete(f"{BASE}/portas/{pp}/conexao", params={"lado": "fundo"}, headers=cab)
    assert (r.json()["status"], r.json()["descricao"], r.json()["fundo"]) == ("up", "Conector RJ45: SW-5A · 7", None)
    r = cliente.delete(f"{BASE}/portas/{pp}/conexao", params={"lado": "frente"}, headers=cab)
    assert (r.json()["status"], r.json()["descricao"]) == ("down", "Desligado")
    assert (_porta(cliente, cab, sw)["status"], _porta(cliente, cab, sw)["descricao"]) == ("down", "Desligado")
    assert cliente.delete(f"{BASE}/portas/{pp}/conexao", params={"lado": "frente"}, headers=cab).status_code == 404


def test_desligar_nao_deixa_equipamento_sem_cabo_para_cima(cliente, admin):
    c = _cenario(cliente, admin)
    cab = c["cab"]["analista"]
    subida = c["switch"]["portas"][8]["id"]
    r = cliente.delete(f"{BASE}/portas/{subida}/conexao", headers=cab)
    assert (r.status_code, r.json()["codigo"]) == (409, "unica_ligacao_para_cima") and "SW-5A" in r.json()["detalhe"]
    # Liga antes um segundo cabo para cima (atravessando o patch panel) e aí desliga o primeiro
    pp = c["patch"]["portas"][0]["id"]
    cliente.post(f"{BASE}/portas/{pp}/conexao", json={"lado": "fundo", "porta_id": c["dist"]["portas"][1]["id"]}, headers=cab)
    cliente.post(f"{BASE}/portas/{pp}/conexao", json={"lado": "frente", "porta_id": c["switch"]["portas"][9]["id"]}, headers=cab)
    r = cliente.delete(f"{BASE}/portas/{subida}/conexao", headers=cab)
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["descricao"], r.json()["modo"], r.json()["vlans_tag"]) == ("down", "Desligado", "access", [])
    # Agora o único cabo passa pelo patch panel: nenhum dos lados dele pode ser desligado
    assert cliente.delete(f"{BASE}/portas/{pp}/conexao", params={"lado": "fundo"}, headers=cab).json()["codigo"] == "unica_ligacao_para_cima"
    assert cliente.delete(f"{BASE}/portas/{pp}/conexao", params={"lado": "frente"}, headers=cab).json()["codigo"] == "unica_ligacao_para_cima"
    # Cabo para baixo (um dispositivo) desliga normalmente
    porta = c["switch"]["portas"][3]["id"]
    cliente.post(f"{BASE}/portas/{porta}/conexao", json={"descricao": "Telefone"}, headers=cab)
    assert cliente.delete(f"{BASE}/portas/{porta}/conexao", headers=cab).status_code == 200


def test_excluir_equipamento_nao_quebra_a_cadeia(cliente, admin):
    c = _cenario(cliente, admin)
    # A distribuição sustenta o SW-5A: não sai; o SW-5A (folha) sai e a porta do outro lado fica em branco
    r = cliente.delete(f"{BASE}/equipamentos/{c['dist']['id']}", headers=admin)
    assert (r.status_code, r.json()["codigo"]) == (409, "unica_ligacao_para_cima")
    assert cliente.delete(f"{BASE}/equipamentos/{c['switch']['id']}", headers=admin).status_code == 204
    porta = _porta(cliente, admin, c["dist"]["portas"][0]["id"])
    assert (porta["status"], porta["descricao"], porta["modo"], porta["conexao"]) == ("down", "Desligado", "access", None)
    assert cliente.delete(f"{BASE}/equipamentos/{c['dist']['id']}", headers=admin).status_code == 204


def test_bem_do_patrimonio_e_dispositivos_atras(cliente, admin):
    """Bem ligado no fundo do patch panel, o PC atrás do telefone e o cadastro do bem mostrando onde está."""
    from app.models.patrimonio import Bem, Localizacao
    c = _cenario(cliente, admin)
    with FabricaSessao() as sessao:
        sala = Localizacao(tipo="sala", nome="Sala 05A03", codigo="05A03", andar=5, lado="A")
        sessao.add(sala)
        sessao.flush()
        telefone = Bem(chapa="012345", descricao="Telefone IP", localizacao_id=sala.id, conservacao=1)
        pc = Bem(chapa="067890", descricao="Computador", localizacao_id=sala.id, conservacao=1)
        sessao.add_all([telefone, pc])
        sessao.commit()
        tel_id, pc_id = str(telefone.id), str(pc.id)
    achados = cliente.get(f"{BASE}/bens", params={"busca": "0123"}, headers=c["cab"]["leitor"]).json()
    assert achados == [{"id": tel_id, "chapa": "012345", "descricao": "Telefone IP", "sala": "Sala 05A03"}]
    pp, cab = c["patch"]["portas"][4]["id"], c["cab"]["analista"]
    assert cliente.post(f"{BASE}/portas/{pp}/conexao/atras", json={"lado": "fundo", "bem_id": pc_id}, headers=cab).json()["codigo"] == "sem_dispositivo"
    r = cliente.post(f"{BASE}/portas/{pp}/conexao", json={"lado": "fundo", "bem_id": tel_id}, headers=cab)
    assert r.json()["descricao"] == "Terminal Punch Down: Telefone IP (chapa 012345)"
    r = cliente.post(f"{BASE}/portas/{pp}/conexao/atras", json={"lado": "fundo", "bem_id": pc_id}, headers=cab)
    assert r.status_code == 201, r.text
    assert [x["texto"] for x in r.json()["fundo"]["atras"]] == ["Computador (chapa 067890)"]
    assert cliente.post(f"{BASE}/portas/{pp}/conexao/atras", json={"lado": "fundo", "bem_id": tel_id}, headers=cab).json()["codigo"] == "duplicado"
    do_pc = cliente.get(f"{BASE}/bens/{pc_id}/portas", headers=c["cab"]["leitor"]).json()[0]
    assert (do_pc["atras_de"], do_pc["lado"], do_pc["equipamento_nome"]) == ("Telefone IP (chapa 012345)", "fundo", "PP-5A")
    do_tel = cliente.get(f"{BASE}/bens/{tel_id}/portas", headers=c["cab"]["leitor"]).json()[0]
    assert (do_tel["atras_de"], do_tel["lado"]) == ("", "fundo")
    r = cliente.delete(f"{BASE}/portas/{pp}/conexao/atras/{do_pc['dispositivo_id']}", headers=cab)
    assert r.json()["fundo"]["atras"] == []
    assert cliente.delete(f"{BASE}/portas/{pp}/conexao", params={"lado": "fundo"}, headers=cab).json()["descricao"] == "Desligado"
    assert cliente.get(f"{BASE}/bens/{tel_id}/portas", headers=c["cab"]["leitor"]).json() == []
    assert cliente.get(f"{BASE}/bens/{uuid.uuid4()}/portas", headers=c["cab"]["leitor"]).status_code == 404


# ---------------------------------------------------------------------------------------------
# Caminho e topologia
# ---------------------------------------------------------------------------------------------

def test_caminho_segue_o_fio_de_cada_porta(cliente, admin):
    """Core → distribuição → acesso → patch panel (frente → fundo) → dispositivo; porta de patch panel sem switch para no aviso."""
    c = _cenario(cliente, admin)
    sw, pp, cab, leitor = c["switch"]["portas"], c["patch"]["portas"], c["cab"]["analista"], c["cab"]["leitor"]
    cliente.post(f"{BASE}/portas/{pp[2]['id']}/conexao", json={"lado": "frente", "porta_id": sw[6]["id"]}, headers=cab)
    cliente.post(f"{BASE}/portas/{pp[2]['id']}/conexao", json={"lado": "fundo", "descricao": "Tomada 5A-12"}, headers=cab)
    cliente.post(f"{BASE}/portas/{sw[3]['id']}/conexao", json={"descricao": "Telefone IP"}, headers=cab)
    cliente.post(f"{BASE}/portas/{sw[3]['id']}/conexao/atras", json={"descricao": "Computador"}, headers=cab)
    x = cliente.get(f"{BASE}/portas/{sw[3]['id']}/caminho", headers=leitor).json()
    assert [(e["nome"], e["cabo"]) for e in x["etapas"]] == [("SW-CORE", ""), ("SW-DIST", "1 ↔ SFP 1"), ("SW-5A", "1 ↔ SFP 1")]
    assert [d["texto"] for d in x["dispositivos"]] == ["Telefone IP", "Computador"] and x["cabo_dispositivos"] == "4" and x["aviso"] == ""
    # Da porta do patch panel e da porta do switch que vai a ele: o mesmo caminho, atravessando a porta do patch panel
    for p in (pp[2]["id"], sw[6]["id"]):
        x = cliente.get(f"{BASE}/portas/{p}/caminho", headers=leitor).json()
        assert [e["nome"] for e in x["etapas"]] == ["SW-CORE", "SW-DIST", "SW-5A", "PP-5A"]
        assert (x["etapas"][3]["cabo"], x["etapas"][3]["lado_entrada"], x["etapas"][3]["lado_saida"]) == ("7 ↔ 3 (Conector RJ45)", "frente", "fundo")
        assert [d["texto"] for d in x["dispositivos"]] == ["Tomada 5A-12"] and x["cabo_dispositivos"] == "3 (Terminal Punch Down)"
    # Outra porta do mesmo patch panel, só com o telefone no fundo: não usa o cabo da porta 3
    cliente.post(f"{BASE}/portas/{pp[5]['id']}/conexao", json={"lado": "fundo", "descricao": "VOIP 08395"}, headers=cab)
    x = cliente.get(f"{BASE}/portas/{pp[5]['id']}/caminho", headers=leitor).json()
    assert [e["nome"] for e in x["etapas"]] == ["PP-5A"] and "não chega a nenhum switch" in x["aviso"]
    # A porta de subida do switch: o caminho para nele
    x = cliente.get(f"{BASE}/portas/{sw[8]['id']}/caminho", headers=leitor).json()
    assert x["etapas"][-1]["nome"] == "SW-5A" and x["etapas"][-1]["porta_saida"] is None


def test_topologia_por_camadas(cliente, admin):
    """Core no topo, distribuição, acesso e o patch panel no fim do ramo; patch panel no meio quando o cabo passa por ele."""
    c = _cenario(cliente, admin)
    pp, cab = c["patch"]["portas"], c["cab"]["analista"]
    cliente.post(f"{BASE}/portas/{pp[0]['id']}/conexao", json={"lado": "frente", "porta_id": c["switch"]["portas"][4]["id"]}, headers=cab)
    painel2 = _novo(cliente, admin, "PP-MEIO", c["painel"]["id"], tipo="patch_panel").json()
    cliente.post(f"{BASE}/portas/{painel2['portas'][0]['id']}/conexao", json={"lado": "fundo", "porta_id": c["dist"]["portas"][2]["id"]}, headers=cab)
    _novo(cliente, admin, "SW-6A", c["modelo"]["id"], "acesso", ligacao=_lig(9, painel2["portas"][0]["id"], "frente"))
    t = cliente.get(f"{BASE}/topologia", headers=c["cab"]["leitor"]).json()
    assert [n["nome"] for n in t["raizes"]] == ["SW-CORE"] and t["sem_ligacao"] == []
    dist = t["raizes"][0]["filhos"][0]
    assert dist["nome"] == "SW-DIST" and [f["nome"] for f in dist["filhos"]] == ["SW-5A", "PP-MEIO"]
    assert [f["nome"] for f in dist["filhos"][0]["filhos"]] == ["PP-5A"] and [f["nome"] for f in dist["filhos"][1]["filhos"]] == ["SW-6A"]


def test_nucleo_pela_funcao_com_alta_disponibilidade(cliente, admin):
    """Cores lado a lado (Primário primeiro); Primário fora do ar no ping: o Secundário assume a frente."""
    from app.services.rede import ping
    modelo = cliente.post(f"{BASE}/modelos", json={"nome": "Switch 10", "linhas": 2, "colunas": 5}, headers=admin).json()["id"]
    novo = lambda nome, ip, funcao, ligacao=None: cliente.post(f"{BASE}/equipamentos", json={
        "nome": nome, "modelo_face_id": modelo, "ip_gerencia": ip, "funcao": funcao, "ligacao": ligacao}, headers=admin).json()
    primario = novo("Z-CORE-1", "10.23.1.1", "core_primario")
    secundario = novo("Y-CORE-2", "10.23.1.2", "core_secundario", _lig(9, primario["portas"][8]["id"]))
    dist = novo("A-DIST", "10.23.2.1", "distribuicao", _lig(1, primario["portas"][0]["id"]))
    cliente.post(f"{BASE}/portas/{secundario['portas'][0]['id']}/conexao", json={"porta_id": dist["portas"][1]["id"]}, headers=admin)
    novo("SW-5A", "10.23.5.2", "acesso", _lig(1, secundario["portas"][1]["id"]))
    t = cliente.get(f"{BASE}/topologia", headers=admin).json()
    assert [(n["nome"], n["assumiu"]) for n in t["raizes"]] == [("Z-CORE-1", False), ("Y-CORE-2", False)]
    assert [f["nome"] for f in t["raizes"][0]["filhos"]] == ["A-DIST"] and [f["nome"] for f in t["raizes"][1]["filhos"]] == ["SW-5A"]
    no_ar = {"10.23.1.2", "10.23.2.1", "10.23.5.2"}
    for _ in range(3):
        with FabricaSessao() as sessao:
            ping.testar_todos(sessao, testar=lambda ip: ip in no_ar)
            sessao.commit()
    t = cliente.get(f"{BASE}/topologia", headers=admin).json()
    assert [(n["nome"], n["assumiu"], n["ping_situacao"]) for n in t["raizes"]] == [("Y-CORE-2", True, "no_ar"), ("Z-CORE-1", False, "fora")]


# ---------------------------------------------------------------------------------------------
# Pontos, chamados, indicadores, cargas desativadas e cadastros de apoio
# ---------------------------------------------------------------------------------------------

def test_ponto_de_rede_e_chamado_da_porta(cliente, admin):
    c = _cenario(cliente, admin)
    pp, cab = c["patch"]["portas"][2]["id"], c["cab"]["analista"]
    cliente.post(f"{BASE}/portas/{pp}/conexao", json={"lado": "frente", "porta_id": c["switch"]["portas"][6]["id"]}, headers=cab)
    ponto = cliente.post(f"{BASE}/pontos", json={"codigo": "5a-12", "porta_id": pp}, headers=cab)
    assert ponto.status_code == 201 and ponto.json()["codigo"] == "5A-12" and ponto.json()["caminho"] == ["PP-5A · porta 3", "SW-5A · porta 7"]
    assert cliente.post(f"{BASE}/pontos", json={"codigo": "5A-13", "porta_id": pp}, headers=cab).json()["codigo"] == "porta_ocupada"
    ch = _preparar(cliente, admin)
    porta = c["switch"]["portas"][1]["id"]
    r = _abrir(cliente, ch["cab"]["solicitante"], ch["ids"]["categoria"], titulo="Ponto sem rede", rede_porta_id=porta)
    assert r.status_code == 201, r.text
    assert [x["titulo"] for x in _porta(cliente, admin, porta)["chamados"]] == ["Ponto sem rede"]
    assert _porta(cliente, c["cab"]["leitor"], porta)["chamados"] == []
    assert cliente.get(f"{CHAMADOS}/{r.json()['numero']}", headers=admin).status_code == 200


def test_indicadores_portas_alteradas_e_patch_panel_com_um_lado(cliente, admin):
    c = _cenario(cliente, admin)
    cab = c["cab"]["analista"]
    assert cliente.get(f"{BASE}/indicadores", headers=c["cab"]["leitor"]).json()["portas_patch_um_lado"] == 0
    pp = c["patch"]["portas"]
    cliente.post(f"{BASE}/portas/{pp[0]['id']}/conexao", json={"lado": "fundo", "descricao": "Tomada 5A-01"}, headers=cab)
    cliente.post(f"{BASE}/portas/{pp[1]['id']}/conexao", json={"lado": "fundo", "descricao": "Tomada 5A-02"}, headers=cab)
    cliente.post(f"{BASE}/portas/{pp[1]['id']}/conexao", json={"lado": "frente", "porta_id": c["switch"]["portas"][1]["id"]}, headers=cab)
    ind = cliente.get(f"{BASE}/indicadores", headers=cab).json()
    assert ind["portas_patch_um_lado"] == 1 and ind["portas_alteradas"] >= 3
    um_lado = cliente.get(f"{BASE}/portas-patch-um-lado", headers=c["cab"]["leitor"]).json()
    assert [(x["equipamento_nome"], x["numero_logico"], x["descricao"]) for x in um_lado] == [("PP-5A", 1, "Terminal Punch Down: Tomada 5A-01")]
    alteradas = {(x["equipamento_nome"], x["numero_logico"]) for x in cliente.get(f"{BASE}/portas-alteradas", headers=cab).json()}
    assert {("PP-5A", 1), ("PP-5A", 2), ("SW-5A", 2)} <= alteradas


def test_cargas_automaticas_desativadas(cliente, admin):
    """LLDP e GLPI criariam equipamentos fora da cadeia: as duas recusam rodar."""
    from app.services.rede import importacao_glpi, importacao_lldp
    with FabricaSessao() as sessao:
        for carga, dados in ((importacao_lldp, {"equipamentos": []}), (importacao_glpi, {})):
            with pytest.raises(servico.ErroRede) as erro:
                carga.carregar(sessao, dados)
            assert erro.value.codigo == "carga_desativada"
        assert sessao.scalar(select(EquipamentoRede).limit(1)) is None


def test_racks_e_posicao_dos_equipamentos(cliente, admin):
    c = _cenario(cliente, admin)
    r = cliente.post(f"{BASE}/racks", json={"nome": "Rack do 5º andar", "cor": "cinza", "altura_u": 12}, headers=admin)
    assert r.status_code == 201 and r.json()["equipamentos"] == 0
    rack = r.json()["id"]
    assert cliente.post(f"{BASE}/racks", json={"nome": "rack do 5º andar"}, headers=admin).status_code == 409
    assert cliente.post(f"{BASE}/racks", json={"nome": "X", "cor": "rosa"}, headers=admin).status_code == 422
    assert cliente.post(f"{BASE}/racks", json={"nome": "Y"}, headers=c["cab"]["analista"]).status_code == 403
    sw = c["switch"]
    corpo = {"nome": "SW-5A", "modelo_face_id": sw["modelo_face_id"], "rack_id": rack, "posicao_u": 10, "ip_gerencia": sw["ip_gerencia"], "funcao": "acesso"}
    r = cliente.put(f"{BASE}/equipamentos/{sw['id']}", json=corpo, headers=admin)
    assert r.status_code == 200 and r.json()["rack_nome"] == "Rack do 5º andar"
    pp = c["patch"]
    corpo_pp = {"nome": "PP-5A", "tipo": "patch_panel", "modelo_face_id": pp["modelo_face_id"], "rack_id": rack}
    assert cliente.put(f"{BASE}/equipamentos/{pp['id']}", json={**corpo_pp, "posicao_u": 10}, headers=admin).json()["codigo"] == "posicao_ocupada"
    assert cliente.put(f"{BASE}/equipamentos/{pp['id']}", json={**corpo_pp, "posicao_u": 13}, headers=admin).status_code == 400
    assert cliente.put(f"{BASE}/equipamentos/{pp['id']}", json={**corpo_pp, "posicao_u": 11}, headers=admin).status_code == 200
    assert cliente.put(f"{BASE}/racks/{rack}", json={"nome": "Rack do 5º andar", "cor": "cinza", "altura_u": 10}, headers=admin).json()["codigo"] == "em_uso"
    assert cliente.delete(f"{BASE}/racks/{rack}", headers=admin).json()["codigo"] == "em_uso"
    lista = cliente.get(f"{BASE}/racks", headers=c["cab"]["leitor"]).json()
    assert lista[0]["equipamentos"] == 2 and lista[0]["cor"] == "cinza"
    from app.models.patrimonio import Localizacao
    with FabricaSessao() as sessao:
        sessao.add_all([Localizacao(tipo="sala", nome="Sala 05A03", codigo="05A03", andar=5, lado="A"),
                        Localizacao(tipo="sala", nome="Sala 00B01", codigo="00B01", andar=0, lado="B")])
        sessao.commit()
    todas = cliente.get(f"{BASE}/salas", params={"todas": True}, headers=c["cab"]["leitor"]).json()
    assert [(x["codigo"], x["andar"]) for x in todas] == [("00B01", 0), ("05A03", 5)] and all(x["rotulo"] for x in todas)


def test_intervalo_do_ping_nos_parametros(cliente, admin):
    """Intervalo entre as rodadas (1 a 60 min, só Controle total); a tarefa pula enquanto o intervalo não passou."""
    from datetime import timedelta

    from app.core.banco import agora_utc
    from app.services.rede import ping

    c = _cenario(cliente, admin)
    assert cliente.get(f"{BASE}/parametros", headers=admin).json() == {"ping_intervalo_min": 1}
    assert cliente.get(f"{BASE}/parametros", headers=c["cab"]["analista"]).status_code == 403
    assert cliente.put(f"{BASE}/parametros", json={"ping_intervalo_min": 61}, headers=admin).status_code == 422
    assert cliente.put(f"{BASE}/parametros", json={"ping_intervalo_min": 5}, headers=admin).json() == {"ping_intervalo_min": 5}
    with FabricaSessao() as sessao:
        assert ping.hora_da_rodada(sessao) is True
        ping.testar_todos(sessao, testar=lambda ip: True)
        sessao.commit()
        agora = agora_utc()
        assert ping.hora_da_rodada(sessao, agora + timedelta(minutes=3)) is False
        assert ping.hora_da_rodada(sessao, agora + timedelta(minutes=5)) is True


def test_vlan_tem_cor_como_os_marcadores(cliente, admin):
    """A VLAN nasce com uma cor sorteada (1–11), troca pela paleta (0–11), mantém a cor quando ela não vem e só quem administra muda."""
    c = _cenario(cliente, admin)
    v10 = c["v10"]
    assert 1 <= v10["cor_indice"] <= 11
    url = f"{BASE}/vlans/{v10['id']}"
    assert cliente.put(url, json={"numero": 10, "nome": "Dados", "cor_indice": 0}, headers=admin).json()["cor_indice"] == 0
    r = cliente.put(url, json={"numero": 10, "nome": "Dados corporativos"}, headers=admin).json()
    assert (r["nome"], r["cor_indice"]) == ("Dados corporativos", 0)
    assert cliente.put(url, json={"numero": 10, "nome": "Dados", "cor_indice": 12}, headers=admin).status_code == 422
    assert cliente.put(url, json={"numero": 10, "nome": "Dados", "cor_indice": 3}, headers=c["cab"]["analista"]).status_code == 403


def test_trocar_ligacao_poe_patch_panel_no_meio_do_cabo(cliente, admin):
    """O cabo CORE ↔ DIST vira CORE ↔ PP (frente) e PP (fundo) ↔ DIST numa troca só; troca que deixaria alguém sem cabo para cima é desfeita."""
    c = _cenario(cliente, admin)
    cab = c["cab"]["analista"]
    dist_subida, core_1, pp = c["dist"]["portas"][8]["id"], c["core"]["portas"][0]["id"], c["patch"]["portas"][4]["id"]
    # Sem religar o antigo, o outro lado do patch panel fica vazio: o SW-DIST perderia o caminho e nada muda
    r = cliente.post(f"{BASE}/portas/{dist_subida}/conexao/trocar", json={"porta_id": pp, "outro_lado": "fundo"}, headers=cab)
    assert (r.status_code, r.json()["codigo"]) == (409, "unica_ligacao_para_cima")
    assert _porta(cliente, cab, dist_subida)["descricao"] == "SW-CORE · 1"
    # Religando o antigo no outro lado (frente), o cabo passa pelo patch panel e a configuração da porta fica
    r = cliente.post(f"{BASE}/portas/{dist_subida}/conexao/trocar", json={"porta_id": pp, "outro_lado": "fundo", "religar_antigo": True}, headers=cab)
    assert r.status_code == 200, r.text
    assert (r.json()["descricao"], r.json()["modo"], r.json()["vlans_tag"]) == ("PP-5A · 5 (Terminal Punch Down)", "trunk", [20])
    assert _porta(cliente, cab, pp)["descricao"] == "Terminal Punch Down: SW-DIST · SFP 1 · Conector RJ45: SW-CORE · 1"
    assert _porta(cliente, cab, core_1)["descricao"] == "PP-5A · 5 (Conector RJ45)"
    caminho = cliente.get(f"{BASE}/portas/{c['switch']['portas'][3]['id']}/caminho", headers=cab).json()
    assert [e["nome"] for e in caminho["etapas"]][:3] == ["SW-CORE", "PP-5A", "SW-DIST"]
    # Troca para um dispositivo: a ponta antiga (o patch panel, lado fundo) perde só aquele lado
    tel = c["switch"]["portas"][3]["id"]
    cliente.post(f"{BASE}/portas/{tel}/conexao", json={"descricao": "Telefone"}, headers=cab)
    r = cliente.post(f"{BASE}/portas/{tel}/conexao/trocar", json={"descricao": "Impressora"}, headers=cab)
    assert r.json()["descricao"] == "Impressora"
    assert cliente.post(f"{BASE}/portas/{c['switch']['portas'][5]['id']}/conexao/trocar", json={"descricao": "X"}, headers=cab).status_code == 404
