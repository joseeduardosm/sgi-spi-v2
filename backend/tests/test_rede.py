# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o plano de face da rede: acesso, modelos, equipamentos, portas, VLANs, conexões, pontos e a carga do GLPI.
"""Plano de face da rede (`/api/rede`)."""

import uuid

from sqlalchemy import func, select

from app.core.banco import FabricaSessao
from app.models.rede import ConexaoRede, EquipamentoRede, PortaRede
from app.services.chamados.importacao_glpi import ler_dump
from app.services.rede import importacao_glpi
from tests.conftest import cabecalho, criar_usuario
from tests.test_chamados import BASE as CHAMADOS, _abrir, _preparar

BASE = "/api/rede"


def _recurso(cliente, admin) -> int:
    r = cliente.post("/api/acl/recursos", json={"nome": "Rede", "slug": "rede"}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _cenario(cliente, admin) -> dict:
    """Modelo 2×4 + 2 SFP, um switch e um patch panel, VLANs 10 e 20; analista (editar) e leitor (ver)."""
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
    switch = cliente.post(f"{BASE}/equipamentos", json={"nome": "SW-5A", "modelo_face_id": modelo.json()["id"], "ip_gerencia": "10.23.5.2", "funcao": "acesso"}, headers=admin)
    assert switch.status_code == 201, switch.text
    patch = cliente.post(f"{BASE}/equipamentos", json={"nome": "PP-5A", "tipo": "patch_panel", "modelo_face_id": painel["id"]}, headers=admin).json()
    v10 = cliente.post(f"{BASE}/vlans", json={"numero": 10, "nome": "Dados"}, headers=admin).json()
    v20 = cliente.post(f"{BASE}/vlans", json={"numero": 20, "nome": "Voz"}, headers=admin).json()
    cab = {k: cabecalho(cliente, k) for k in ("analista", "leitor")}
    return {"ids": ids, "cab": cab, "switch": switch.json(), "patch": patch, "v10": v10, "v20": v20, "modelo": modelo.json()}


def test_modulo_fechado_ate_haver_regras(cliente, admin):
    criar_usuario("curioso")
    cab = cabecalho(cliente, "curioso")
    assert cliente.get(f"{BASE}/contexto", headers=cab).json() == {"ver": False, "editar": False, "administrar": False}
    assert cliente.get(f"{BASE}/equipamentos", headers=cab).status_code == 403
    assert cliente.get(f"{BASE}/contexto", headers=admin).json() == {"ver": True, "editar": True, "administrar": True}


def test_face_gerada_pelo_modelo_e_posicoes(cliente, admin):
    c = _cenario(cliente, admin)
    sw = c["switch"]
    assert [p["numero_logico"] for p in sw["portas"]] == list(range(1, 11)) and sw["portas"][8]["nome"] == "SFP 1"
    # Numeração por coluna: 1 em cima, 2 embaixo, 3 em cima...
    assert sw["posicoes"]["1"] == [1, 1] and sw["posicoes"]["2"] == [2, 1] and sw["posicoes"]["3"] == [1, 2] and "9" not in sw["posicoes"]
    assert c["patch"]["posicoes"]["8"] == [1, 8]
    lista = cliente.get(f"{BASE}/equipamentos", headers=c["cab"]["leitor"]).json()
    assert {e["nome"]: e["portas_total"] for e in lista} == {"PP-5A": 8, "SW-5A": 10} and all(e["altura_u"] == 1 for e in lista)
    # Porta extra com número da grade é recusada; modelo em uso não sai; só quem administra mexe em modelos
    r = cliente.put(f"{BASE}/modelos/{c['modelo']['id']}", json={"nome": "Switch 8+2", "linhas": 2, "colunas": 4, "portas_extras": [{"numero": 8}]}, headers=admin)
    assert r.status_code == 400
    assert cliente.delete(f"{BASE}/modelos/{c['modelo']['id']}", headers=admin).json()["codigo"] == "em_uso"
    assert cliente.post(f"{BASE}/modelos", json={"nome": "X", "linhas": 1, "colunas": 1}, headers=c["cab"]["analista"]).status_code == 403
    assert cliente.post(f"{BASE}/equipamentos", json={"nome": "SW", "ip_gerencia": "999.1.1.1"}, headers=admin).status_code == 400


def test_porta_configuracao_logica(cliente, admin):
    c = _cenario(cliente, admin)
    p1 = c["switch"]["portas"][0]["id"]
    # Access com VLAN com tag é recusado; trunk aceita
    r = cliente.put(f"{BASE}/portas/{p1}", json={"modo": "access", "vlan_nativa_id": c["v10"]["id"], "vlans_tag": [c["v20"]["id"]]}, headers=c["cab"]["analista"])
    assert r.status_code == 400
    r = cliente.put(f"{BASE}/portas/{p1}", json={"descricao": "Uplink do 5º", "modo": "trunk", "vlan_nativa_id": c["v10"]["id"], "vlans_tag": [c["v20"]["id"]],
                                                 "velocidade_mbps": 1000, "duplex": "full", "status": "up"}, headers=c["cab"]["analista"])
    assert r.status_code == 200, r.text
    assert (r.json()["vlan_nativa"], r.json()["vlans_tag"], r.json()["descricao"]) == (10, [20], "Uplink do 5º")
    # VLAN em uso não sai; o leitor não configura
    assert cliente.delete(f"{BASE}/vlans/{c['v20']['id']}", headers=admin).json()["codigo"] == "em_uso"
    assert cliente.put(f"{BASE}/portas/{p1}", json={"modo": "access"}, headers=c["cab"]["leitor"]).status_code == 403
    assert cliente.post(f"{BASE}/vlans", json={"numero": 10}, headers=admin).status_code == 409


def test_conexoes_pontos_e_caminho(cliente, admin):
    c = _cenario(cliente, admin)
    sw7, pp3 = c["switch"]["portas"][6]["id"], c["patch"]["portas"][2]["id"]
    r = cliente.post(f"{BASE}/portas/{pp3}/conexao", json={"porta_id": sw7}, headers=c["cab"]["analista"])
    assert r.status_code == 201 and r.json()["conexao"]["texto"] == "SW-5A · porta 7"
    # A porta do switch já está ocupada (do outro lado)
    outra = c["patch"]["portas"][3]["id"]
    assert cliente.post(f"{BASE}/portas/{outra}/conexao", json={"porta_id": sw7}, headers=c["cab"]["analista"]).json()["codigo"] == "porta_ocupada"
    assert cliente.post(f"{BASE}/portas/{outra}/conexao", json={}, headers=c["cab"]["analista"]).status_code == 400
    ponto = cliente.post(f"{BASE}/pontos", json={"codigo": "5a-12", "porta_id": pp3}, headers=c["cab"]["analista"])
    assert ponto.status_code == 201 and ponto.json()["codigo"] == "5A-12" and ponto.json()["caminho"] == ["PP-5A · porta 3", "SW-5A · porta 7"]
    assert cliente.post(f"{BASE}/pontos", json={"codigo": "5A-13", "porta_id": pp3}, headers=c["cab"]["analista"]).json()["codigo"] == "porta_ocupada"
    face = cliente.get(f"{BASE}/equipamentos/{c['patch']['id']}", headers=c["cab"]["leitor"]).json()
    assert face["portas"][2]["ponto"] == "5A-12" and face["portas"][2]["conexao"]["equipamento_id"] == c["switch"]["id"]
    assert cliente.delete(f"{BASE}/portas/{pp3}/conexao", headers=c["cab"]["analista"]).json()["conexao"] is None
    assert cliente.delete(f"{BASE}/portas/{pp3}/conexao", headers=c["cab"]["analista"]).status_code == 404


def test_chamado_aberto_pela_porta_aparece_nela(cliente, admin):
    c = _cenario(cliente, admin)
    ch = _preparar(cliente, admin)
    porta = c["switch"]["portas"][1]["id"]
    r = _abrir(cliente, ch["cab"]["solicitante"], ch["ids"]["categoria"], titulo="Ponto sem rede", rede_porta_id=porta)
    assert r.status_code == 201, r.text
    assert _abrir(cliente, ch["cab"]["solicitante"], ch["ids"]["categoria"], rede_porta_id="00000000-0000-0000-0000-000000000000").json()["codigo"] == "porta_invalida"
    detalhe = cliente.get(f"{BASE}/portas/{porta}", headers=admin).json()
    assert [x["titulo"] for x in detalhe["chamados"]] == ["Ponto sem rede"]
    assert cliente.get(f"{BASE}/equipamentos/{c['switch']['id']}", headers=admin).json()["portas"][1]["chamados_abertos"] == 1
    # O leitor da rede que não tem papel nos Chamados não vê o chamado (a lista vem vazia)
    assert cliente.get(f"{BASE}/portas/{porta}", headers=c["cab"]["leitor"]).json()["chamados"] == []
    assert cliente.get(f"{CHAMADOS}/{r.json()['numero']}", headers=admin).status_code == 200


DUMP_REDE = """
CREATE TABLE `glpi_configs` (
  `id` int NOT NULL,
  `context` varchar(150) DEFAULT NULL,
  `name` varchar(150) DEFAULT NULL,
  `value` text DEFAULT NULL
);
INSERT INTO `glpi_configs` VALUES (1,'core','version','10.0.18');
CREATE TABLE `glpi_tickets` (
  `id` int NOT NULL
);
CREATE TABLE `glpi_networkequipmentmodels` (
  `id` int NOT NULL,
  `name` varchar(255) DEFAULT NULL
);
INSERT INTO `glpi_networkequipmentmodels` VALUES (1,'Switch 24 + 2 SFP');
CREATE TABLE `glpi_networkequipments` (
  `id` int NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `serial` varchar(255) DEFAULT NULL,
  `otherserial` varchar(255) DEFAULT NULL,
  `comment` text,
  `locations_id` int NOT NULL DEFAULT 0,
  `networkequipmentmodels_id` int NOT NULL DEFAULT 0,
  `is_deleted` tinyint NOT NULL DEFAULT 0,
  `is_template` tinyint NOT NULL DEFAULT 0
);
INSERT INTO `glpi_networkequipments` VALUES (5,'SW-CORE','ABC123',NULL,NULL,0,1,0,0),(6,'SW-ANDAR','DEF456',NULL,NULL,0,1,0,0);
CREATE TABLE `glpi_networkports` (
  `id` int NOT NULL,
  `items_id` int NOT NULL,
  `itemtype` varchar(100) NOT NULL,
  `logical_number` int NOT NULL DEFAULT 0,
  `name` varchar(255) DEFAULT NULL,
  `mac` varchar(255) DEFAULT NULL,
  `is_deleted` tinyint NOT NULL DEFAULT 0,
  `ifspeed` bigint NOT NULL DEFAULT 0,
  `ifinternalstatus` varchar(255) DEFAULT NULL,
  `ifinerrors` bigint NOT NULL DEFAULT 0,
  `ifouterrors` bigint NOT NULL DEFAULT 0,
  `ifstatus` varchar(255) DEFAULT NULL,
  `ifalias` varchar(255) DEFAULT NULL,
  `portduplex` varchar(255) DEFAULT NULL,
  `trunk` tinyint NOT NULL DEFAULT 0,
  `lastup` timestamp NULL DEFAULT NULL
);
INSERT INTO `glpi_networkports` VALUES (100,5,'NetworkEquipment',1,'Gi1/0/1','aa:bb:cc:dd:ee:01',0,1000000000,'1',0,0,'1','Uplink andar','3',1,'2026-10-30 10:00:00'),(101,5,'NetworkEquipment',26,'Te1/1/2','',0,10000000000,'1',3,0,'2','',NULL,0,NULL),(102,6,'NetworkEquipment',1,'Gi0/1','',0,100000000,'2',0,0,'2','Sala 504',NULL,0,NULL),(103,9,'Computer',1,'eth0','',0,0,NULL,0,0,NULL,'',NULL,0,NULL);
CREATE TABLE `glpi_vlans` (
  `id` int NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `comment` text,
  `tag` int NOT NULL DEFAULT 0
);
INSERT INTO `glpi_vlans` VALUES (1,'Dados',NULL,10),(2,'Voz',NULL,20);
CREATE TABLE `glpi_networkports_vlans` (
  `id` int NOT NULL,
  `networkports_id` int NOT NULL,
  `vlans_id` int NOT NULL,
  `tagged` tinyint NOT NULL DEFAULT 0
);
INSERT INTO `glpi_networkports_vlans` VALUES (1,100,1,0),(2,100,2,1),(3,102,1,0);
CREATE TABLE `glpi_networkports_networkports` (
  `id` int NOT NULL,
  `networkports_id_1` int NOT NULL,
  `networkports_id_2` int NOT NULL
);
INSERT INTO `glpi_networkports_networkports` VALUES (1,100,102),(2,103,101);
CREATE TABLE `glpi_locations` (
  `id` int NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `completename` text
);
"""


def test_carga_da_rede_pelo_dump(cliente, admin, tmp_path):
    dump = tmp_path / "glpi.sql"
    dump.write_text(DUMP_REDE, encoding="utf-8")
    dados = ler_dump(dump, importacao_glpi.TABELAS_REDE)
    with FabricaSessao() as sessao:
        rel = importacao_glpi.carregar(sessao, dados)
        sessao.commit()
    assert (rel.destino["equipamentos"], rel.destino["portas"], rel.destino["VLANs"], rel.destino["conexões"]) == (2, 3, 2, 1)
    with FabricaSessao() as sessao:
        core = sessao.scalar(select(EquipamentoRede).where(EquipamentoRede.nome == "SW-CORE"))
        assert core.modelo_face.colunas == 12 and core.modelo_face.portas_extras[1]["numero"] == 26
        p1 = sessao.scalar(select(PortaRede).where(PortaRede.origem_glpi_id == 100))
        assert (p1.modo, p1.status, p1.velocidade_mbps, p1.duplex, p1.descricao) == ("trunk", "up", 1000, "full", "Uplink andar")
        assert sessao.scalar(select(PortaRede).where(PortaRede.origem_glpi_id == 102)).status == "desativada"
        assert sessao.scalar(select(func.count()).select_from(ConexaoRede)) == 1
    # De novo: nada duplicado
    with FabricaSessao() as sessao:
        rel = importacao_glpi.carregar(sessao, dados)
        sessao.commit()
    assert rel.destino["equipamentos"] == 0 and rel.pulados["equipamentos"] == 2
    face = cliente.get(f"{BASE}/equipamentos/{core.id}", headers=admin).json()
    assert face["portas"][0]["vlan_nativa"] == 10 and face["portas"][0]["vlans_tag"] == [20] and face["portas"][0]["conexao"]["texto"] == "SW-ANDAR · porta Gi0/1"


def test_bem_do_patrimonio_ligado_na_porta(cliente, admin):
    import uuid as _uuid
    from app.models.patrimonio import Bem, Localizacao
    c = _cenario(cliente, admin)
    with FabricaSessao() as sessao:
        sala = Localizacao(tipo="sala", nome="Sala 05A03", codigo="05A03", andar=5, lado="A")
        sessao.add(sala); sessao.flush()
        bem = Bem(chapa="012345", descricao="Impressora multifuncional", localizacao_id=sala.id, conservacao=1)
        sessao.add(bem); sessao.commit()
        bem_id = str(bem.id)
    achados = cliente.get(f"{BASE}/bens", params={"busca": "0123"}, headers=c["cab"]["leitor"]).json()
    assert achados == [{"id": bem_id, "chapa": "012345", "descricao": "Impressora multifuncional", "sala": "Sala 05A03"}]
    assert cliente.get(f"{BASE}/bens", params={"busca": "0"}, headers=c["cab"]["leitor"]).json() == []
    porta = c["switch"]["portas"][4]["id"]
    r = cliente.post(f"{BASE}/portas/{porta}/conexao", json={"bem_id": bem_id}, headers=c["cab"]["analista"])
    assert r.status_code == 201 and r.json()["conexao"]["tipo"] == "bem" and "012345" in r.json()["conexao"]["texto"]
    # No cadastro do bem: em qual switch e porta ele está
    assert cliente.get(f"{BASE}/bens/{bem_id}/portas", headers=c["cab"]["leitor"]).json() == [
        {"porta_id": porta, "porta_nome": "5", "equipamento_id": c["switch"]["id"], "equipamento_nome": "SW-5A", "atras_de": "", "dispositivo_id": None}]
    assert cliente.get(f"{BASE}/bens/{_uuid.uuid4()}/portas", headers=c["cab"]["leitor"]).status_code == 404


def test_racks_e_posicao_dos_equipamentos(cliente, admin):
    c = _cenario(cliente, admin)
    r = cliente.post(f"{BASE}/racks", json={"nome": "Rack do 5º andar", "cor": "cinza", "altura_u": 12}, headers=admin)
    assert r.status_code == 201 and r.json()["equipamentos"] == 0
    rack = r.json()["id"]
    assert cliente.post(f"{BASE}/racks", json={"nome": "rack do 5º andar"}, headers=admin).status_code == 409
    assert cliente.post(f"{BASE}/racks", json={"nome": "X", "cor": "rosa"}, headers=admin).status_code == 422
    assert cliente.post(f"{BASE}/racks", json={"nome": "Y"}, headers=c["cab"]["analista"]).status_code == 403
    # Equipamento no rack: posição dentro da altura e sem sobrepor
    sw = c["switch"]
    corpo = {"nome": "SW-5A", "modelo_face_id": sw["modelo_face_id"], "rack_id": rack, "posicao_u": 10, "ip_gerencia": "10.23.5.2", "funcao": "acesso"}
    r = cliente.put(f"{BASE}/equipamentos/{sw['id']}", json=corpo, headers=admin)
    assert r.status_code == 200 and r.json()["rack_nome"] == "Rack do 5º andar"
    pp = c["patch"]
    corpo_pp = {"nome": "PP-5A", "tipo": "patch_panel", "modelo_face_id": pp["modelo_face_id"], "rack_id": rack}
    assert cliente.put(f"{BASE}/equipamentos/{pp['id']}", json={**corpo_pp, "posicao_u": 10}, headers=admin).json()["codigo"] == "posicao_ocupada"
    assert cliente.put(f"{BASE}/equipamentos/{pp['id']}", json={**corpo_pp, "posicao_u": 13}, headers=admin).status_code == 400
    assert cliente.put(f"{BASE}/equipamentos/{pp['id']}", json={**corpo_pp, "posicao_u": 11}, headers=admin).status_code == 200
    # Posição sem rack não vale; rack com equipamento não sai nem encolhe para fora deles
    assert cliente.post(f"{BASE}/equipamentos", json={"nome": "SW-X", "posicao_u": 3}, headers=admin).status_code == 400
    assert cliente.put(f"{BASE}/racks/{rack}", json={"nome": "Rack do 5º andar", "cor": "cinza", "altura_u": 10}, headers=admin).json()["codigo"] == "em_uso"
    assert cliente.delete(f"{BASE}/racks/{rack}", headers=admin).json()["codigo"] == "em_uso"
    lista = cliente.get(f"{BASE}/racks", headers=c["cab"]["leitor"]).json()
    assert lista[0]["equipamentos"] == 2 and lista[0]["cor"] == "cinza"
    assert cliente.get(f"{BASE}/salas", params={"busca": "x"}, headers=c["cab"]["leitor"]).json() == []
    # Lista inteira para o campo de sala (filtra na tela), com rótulo e andar para agrupar
    from app.models.patrimonio import Localizacao
    with FabricaSessao() as sessao:
        sessao.add_all([Localizacao(tipo="sala", nome="Sala 05A03", codigo="05A03", andar=5, lado="A"),
                        Localizacao(tipo="sala", nome="Sala 00B01", codigo="00B01", andar=0, lado="B")])
        sessao.commit()
    todas = cliente.get(f"{BASE}/salas", params={"todas": True}, headers=c["cab"]["leitor"]).json()
    assert [(x["codigo"], x["andar"]) for x in todas] == [("00B01", 0), ("05A03", 5)] and all(x["rotulo"] for x in todas)


def test_topologia_montada_pelas_conexoes(cliente, admin):
    """Núcleo no topo, cascata switch → switch → patch panel, uplink redundante em `tambem_ligado` e os soltos em `sem_ligacao`."""
    c = _cenario(cliente, admin)
    modelo = c["modelo"]["id"]
    ips = iter(range(10, 99))
    novo = lambda nome, tipo="switch", funcao="acesso": cliente.post(f"{BASE}/equipamentos", json={
        "nome": nome, "tipo": tipo, "modelo_face_id": modelo, "ip_gerencia": f"10.23.9.{next(ips)}", "funcao": funcao}, headers=admin).json()
    # Sem core marcado: vale o núcleo automático (o que tem mais switches vizinhos)
    nucleo, andar, andar7, solto = novo("SW-CORE", funcao="distribuicao"), novo("SW-6A"), novo("SW-7A"), novo("PP-SOLTO", "patch_panel")
    porta = lambda e, n: e["portas"][n - 1]["id"]
    ligar = lambda a, b: cliente.post(f"{BASE}/portas/{a}/conexao", json={"porta_id": b}, headers=c["cab"]["analista"])
    # Núcleo ↔ SW-5A e núcleo ↔ SW-6A pela fibra; SW-5A ↔ PP-5A; SW-6A também ligado ao SW-5A (redundância)
    for a, b in ((porta(c["switch"], 9), porta(nucleo, 1)), (porta(andar, 9), porta(nucleo, 2)), (porta(c["patch"], 3), porta(c["switch"], 7)),
                 (porta(andar, 10), porta(c["switch"], 10)), (porta(andar7, 9), porta(nucleo, 3))):
        assert ligar(a, b).status_code == 201
    cliente.post(f"{BASE}/pontos", json={"codigo": "5A-12", "porta_id": porta(c["patch"], 3)}, headers=c["cab"]["analista"])

    r = cliente.get(f"{BASE}/topologia", headers=c["cab"]["leitor"])
    assert r.status_code == 200, r.text
    t = r.json()
    assert [n["nome"] for n in t["raizes"]] == ["SW-CORE"] and [n["nome"] for n in t["sem_ligacao"]] == ["PP-SOLTO"]
    raiz = t["raizes"][0]
    assert raiz["porta_acima"] == "" and [f["nome"] for f in raiz["filhos"]] == ["SW-5A", "SW-6A", "SW-7A"]
    sw5, sw6, _ = raiz["filhos"]
    assert (sw5["porta_acima"], sw5["porta_no_pai"], sw5["cabos_com_pai"]) == ("SFP 1", "1", 1)
    assert [f["nome"] for f in sw5["filhos"]] == ["PP-5A"] and sw5["filhos"][0]["pontos"] == 1 and sw5["filhos"][0]["porta_acima"] == "3"
    # O cabo SW-6A ↔ SW-5A não duplica o SW-6A na árvore: aparece como ligação a mais dos dois lados
    assert sw6["filhos"] == [] and sw6["tambem_ligado"] == ["SW-5A"] and sw5["tambem_ligado"] == ["SW-6A"]
    assert cliente.get(f"{BASE}/topologia").status_code == 401
    # Escolhendo outro núcleo, a árvore vira de cabeça para baixo a partir dele
    t = cliente.get(f"{BASE}/topologia", params={"raiz_id": andar["id"]}, headers=c["cab"]["leitor"]).json()
    # Filhos em ordem de camada: a distribuição (SW-CORE) antes do acesso (SW-5A)
    assert t["raizes"][0]["nome"] == "SW-6A" and [f["nome"] for f in t["raizes"][0]["filhos"]] == ["SW-CORE", "SW-5A"]


def test_cadastro_exige_ip_e_funcao_menos_no_patch_panel(cliente, admin):
    """Todo equipamento menos patch panel exige IP de gerência e função; access point é tipo; os antigos aparecem como incompletos."""
    c = _cenario(cliente, admin)
    base = {"nome": "AP-5A", "tipo": "access_point"}
    assert "IP de gerência" in cliente.post(f"{BASE}/equipamentos", json=base, headers=admin).json()["detalhe"]
    assert "função" in cliente.post(f"{BASE}/equipamentos", json={**base, "ip_gerencia": "10.23.5.50"}, headers=admin).json()["detalhe"]
    r = cliente.post(f"{BASE}/equipamentos", json={**base, "ip_gerencia": "10.23.5.50", "funcao": "acesso"}, headers=admin)
    assert r.status_code == 201 and r.json()["tipo"] == "access_point" and r.json()["cadastro_incompleto"] is False
    # Patch panel: sem IP e sem função (a função mandada é ignorada)
    r = cliente.post(f"{BASE}/equipamentos", json={"nome": "PP-X", "tipo": "patch_panel", "funcao": "acesso"}, headers=admin)
    assert r.status_code == 201 and r.json()["funcao"] is None
    # Cadastro de antes da regra (sem função): aparece incompleto até a próxima edição
    with FabricaSessao() as sessao:
        sessao.add(EquipamentoRede(nome="SW-ANTIGO", tipo="switch"))
        sessao.commit()
    lista = {e["nome"]: e for e in cliente.get(f"{BASE}/equipamentos", headers=c["cab"]["leitor"]).json()}
    assert lista["SW-ANTIGO"]["cadastro_incompleto"] is True and lista["PP-X"]["cadastro_incompleto"] is False


def test_nucleo_pela_funcao_com_alta_disponibilidade(cliente, admin):
    """Cores lado a lado (Primário primeiro, sem olhar cabos nem nome); Primário fora do ar no ping: o Secundário assume a frente."""
    from app.services.rede import ping

    c = _cenario(cliente, admin)
    modelo = c["modelo"]["id"]
    novo = lambda nome, ip, funcao: cliente.post(f"{BASE}/equipamentos", json={"nome": nome, "modelo_face_id": modelo, "ip_gerencia": ip, "funcao": funcao},
                                                 headers=admin).json()
    # Nomes de propósito ao contrário da ordem alfabética
    primario, secundario, dist = novo("Z-CORE-1", "10.23.1.1", "core_primario"), novo("Y-CORE-2", "10.23.1.2", "core_secundario"), novo("A-DIST", "10.23.2.1", "distribuicao")
    porta = lambda e, n: e["portas"][n - 1]["id"]
    ligar = lambda a, b: cliente.post(f"{BASE}/portas/{a}/conexao", json={"porta_id": b}, headers=c["cab"]["analista"])
    # Os dois cores ligados entre si e à distribuição (o secundário com mais cabos); SW-5A (acesso) embaixo da distribuição
    for a, b in ((porta(primario, 9), porta(secundario, 9)), (porta(primario, 1), porta(dist, 1)), (porta(secundario, 1), porta(dist, 2)),
                 (porta(secundario, 2), porta(c["switch"], 1)), (porta(dist, 3), porta(c["switch"], 2))):
        assert ligar(a, b).status_code == 201
    t = cliente.get(f"{BASE}/topologia", headers=c["cab"]["leitor"]).json()
    assert [(n["nome"], n["funcao"], n["assumiu"]) for n in t["raizes"]] == [("Z-CORE-1", "core_primario", False), ("Y-CORE-2", "core_secundario", False)]
    assert [f["nome"] for f in t["raizes"][0]["filhos"]] == ["A-DIST"] and [f["nome"] for f in t["raizes"][1]["filhos"]] == ["SW-5A"]
    assert t["raizes"][0]["tambem_ligado"] == ["Y-CORE-2"]

    # Ping: 2 falhas ainda não derrubam; a 3ª dá "fora do ar" e o Secundário passa à frente; a primeira resposta volta ao normal
    no_ar = {"10.23.1.2", "10.23.2.1", "10.23.5.2"}
    for rodada in range(3):
        with FabricaSessao() as sessao:
            ping.testar_todos(sessao, testar=lambda ip: ip in no_ar)
            sessao.commit()
        situacao = cliente.get(f"{BASE}/equipamentos/{primario['id']}", headers=c["cab"]["leitor"]).json()["ping_situacao"]
        assert situacao == ("fora" if rodada == 2 else None)
    t = cliente.get(f"{BASE}/topologia", headers=c["cab"]["leitor"]).json()
    assert [(n["nome"], n["assumiu"], n["ping_situacao"]) for n in t["raizes"]] == [("Y-CORE-2", True, "no_ar"), ("Z-CORE-1", False, "fora")]
    with FabricaSessao() as sessao:
        ping.testar_todos(sessao, testar=lambda ip: True)
        sessao.commit()
        assert sessao.get(EquipamentoRede, uuid.UUID(primario["id"])).ping_falhas == 0
    assert cliente.get(f"{BASE}/topologia", headers=c["cab"]["leitor"]).json()["raizes"][0]["nome"] == "Z-CORE-1"
    # Trocar o IP zera o resultado antigo
    corpo = {"nome": "Z-CORE-1", "modelo_face_id": modelo, "ip_gerencia": "10.23.1.9", "funcao": "core_primario"}
    assert cliente.put(f"{BASE}/equipamentos/{primario['id']}", json=corpo, headers=admin).json()["ping_situacao"] is None


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


def test_ligacao_confere_as_duas_portas(cliente, admin):
    """Porta descrita no switch (dispositivo provável) só liga confirmando; porta já ligada nunca; bem numa porta descrita liga direto."""
    c = _cenario(cliente, admin)
    nucleo = cliente.post(f"{BASE}/equipamentos", json={"nome": "SW-CORE", "modelo_face_id": c["modelo"]["id"], "ip_gerencia": "10.23.1.1",
                                                        "funcao": "core_primario"}, headers=admin).json()
    destino = c["switch"]["portas"][0]["id"]
    cliente.put(f"{BASE}/portas/{destino}", json={"descricao": "Sala 05B05 - Impressora", "modo": "access", "status": "up"}, headers=c["cab"]["analista"])
    origem = nucleo["portas"][0]["id"]
    r = cliente.post(f"{BASE}/portas/{origem}/conexao", json={"porta_id": destino}, headers=c["cab"]["analista"])
    assert r.status_code == 409 and r.json()["codigo"] == "porta_com_dispositivo"
    assert "1 do SW-5A" in r.json()["detalhe"] and "Sala 05B05 - Impressora" in r.json()["detalhe"]
    assert cliente.post(f"{BASE}/portas/{origem}/conexao", json={"porta_id": destino, "forcar": True}, headers=c["cab"]["analista"]).status_code == 201
    # Já ligada (pelo outro lado): recusada mesmo forçando, dizendo qual porta
    r = cliente.post(f"{BASE}/portas/{nucleo['portas'][1]['id']}/conexao", json={"porta_id": destino, "forcar": True}, headers=c["cab"]["analista"])
    assert r.json()["codigo"] == "porta_ocupada" and "1 do SW-5A" in r.json()["detalhe"]
    # Descrição na porta de um bem/texto é o próprio dispositivo: liga sem perguntar
    outra = c["switch"]["portas"][1]["id"]
    cliente.put(f"{BASE}/portas/{outra}", json={"descricao": "Telefone", "modo": "access"}, headers=c["cab"]["analista"])
    assert cliente.post(f"{BASE}/portas/{outra}/conexao", json={"descricao": "Telefone da recepção"}, headers=c["cab"]["analista"]).status_code == 201


def test_modos_de_porta_das_marcas(cliente, admin):
    """Hybrid (Huawei/3Com), QinQ, DTP (Cisco) e roteada: o que cada modo aceita, VLAN de voz e IP da interface."""
    c = _cenario(cliente, admin)
    porta, cab = c["switch"]["portas"][0]["id"], c["cab"]["analista"]
    v10, v20 = c["v10"]["id"], c["v20"]["id"]
    v30 = cliente.post(f"{BASE}/vlans", json={"numero": 30, "nome": "Câmeras"}, headers=admin).json()["id"]
    put = lambda corpo: cliente.put(f"{BASE}/portas/{porta}", json={"descricao": "Uplink", **corpo}, headers=cab)
    # Hybrid: PVID, sem tag e com tag na mesma porta, mais a voz
    r = put({"modo": "hybrid", "vlan_nativa_id": v10, "vlans_sem_tag": [v30], "vlans_tag": [v20], "vlan_voz_id": v20})
    assert r.status_code == 200, r.text
    assert (r.json()["modo"], r.json()["vlan_nativa"], r.json()["vlans_sem_tag"], r.json()["vlans_tag"], r.json()["vlan_voz"]) == ("hybrid", 10, [30], [20], 20)
    assert put({"modo": "hybrid", "vlans_sem_tag": [v30], "vlans_tag": [v30]}).status_code == 400
    # Sem tag extra só na hybrid; com tag não na access/QinQ; voz não na trunk
    assert put({"modo": "trunk", "vlans_sem_tag": [v30]}).status_code == 400
    assert put({"modo": "dot1q_tunnel", "vlan_nativa_id": v30, "vlans_tag": [v20]}).status_code == 400
    assert put({"modo": "trunk", "vlan_voz_id": v20}).status_code == 400
    assert put({"modo": "access", "vlan_nativa_id": v10, "vlan_voz_id": v20}).json()["vlan_voz"] == 20
    assert put({"modo": "dinamico_desejavel", "vlan_nativa_id": v10, "vlans_tag": [v20]}).json()["vlans_tag"] == [20]
    # Roteada: sem VLAN, com IP válido (normalizado); IP só na roteada
    assert put({"modo": "roteada", "vlan_nativa_id": v10}).status_code == 400
    assert put({"modo": "roteada", "ip_interface": "10.23.0.300/30"}).status_code == 400
    assert put({"modo": "access", "ip_interface": "10.23.0.1/30"}).status_code == 400
    r = put({"modo": "roteada", "ip_interface": "10.23.0.1/30"})
    assert (r.json()["modo"], r.json()["ip_interface"], r.json()["vlans_tag"], r.json()["vlan_nativa"]) == ("roteada", "10.23.0.1/30", [], None)
    assert put({"modo": "qualquer"}).status_code == 422
    # VLAN usada como voz não sai
    put({"modo": "access", "vlan_voz_id": v30})
    assert cliente.delete(f"{BASE}/vlans/{v30}", headers=admin).json()["codigo"] == "em_uso"


def test_dois_dispositivos_na_mesma_porta(cliente, admin):
    """Switch → telefone IP → PC: o telefone é a ligação; o PC fica atrás dele. O cadastro do bem mostra "atrás de"; desligar tira todos."""
    from app.models.patrimonio import Bem, Localizacao
    c = _cenario(cliente, admin)
    with FabricaSessao() as sessao:
        sala = Localizacao(tipo="sala", nome="Sala 05A03", codigo="05A03", andar=5, lado="A")
        sessao.add(sala); sessao.flush()
        telefone = Bem(chapa="012345", descricao="Telefone IP", localizacao_id=sala.id, conservacao=1)
        pc = Bem(chapa="067890", descricao="Computador", localizacao_id=sala.id, conservacao=1)
        sessao.add_all([telefone, pc]); sessao.commit()
        tel_id, pc_id = str(telefone.id), str(pc.id)
    porta, cab = c["switch"]["portas"][4]["id"], c["cab"]["analista"]
    # Sem primeiro dispositivo não há "atrás"
    assert cliente.post(f"{BASE}/portas/{porta}/conexao/atras", json={"bem_id": pc_id}, headers=cab).json()["codigo"] == "sem_dispositivo"
    cliente.post(f"{BASE}/portas/{porta}/conexao", json={"bem_id": tel_id}, headers=cab)
    r = cliente.post(f"{BASE}/portas/{porta}/conexao/atras", json={"bem_id": pc_id}, headers=cab)
    assert r.status_code == 201, r.text
    conexao = r.json()["conexao"]
    assert "Telefone IP" in conexao["texto"] and [x["texto"] for x in conexao["atras"]] == ["Computador (chapa 067890)"]
    assert cliente.post(f"{BASE}/portas/{porta}/conexao/atras", json={"bem_id": tel_id}, headers=cab).json()["codigo"] == "duplicado"
    r = cliente.post(f"{BASE}/portas/{porta}/conexao/atras", json={"descricao": "Impressora do PC"}, headers=cab)
    assert [x["ordem"] for x in r.json()["conexao"]["atras"]] == [1, 2]
    # O cadastro do PC mostra a porta e atrás de quem ele está
    do_pc = cliente.get(f"{BASE}/bens/{pc_id}/portas", headers=c["cab"]["leitor"]).json()[0]
    assert do_pc["atras_de"] == "Telefone IP (chapa 012345)" and do_pc["dispositivo_id"] == r.json()["conexao"]["atras"][0]["id"]
    assert cliente.get(f"{BASE}/bens/{tel_id}/portas", headers=c["cab"]["leitor"]).json()[0]["atras_de"] == ""
    # Tirar o PC: a impressora sobe para a posição 1; a topologia conta os bens da porta
    primeiro = r.json()["conexao"]["atras"][0]["id"]
    r = cliente.delete(f"{BASE}/portas/{porta}/conexao/atras/{primeiro}", headers=cab)
    assert [(x["ordem"], x["texto"]) for x in r.json()["conexao"]["atras"]] == [(1, "Impressora do PC")]
    assert cliente.post(f"{BASE}/portas/{porta}/conexao/atras", json={"bem_id": pc_id}, headers=c["cab"]["leitor"]).status_code == 403
    # Desligar a porta tira todos
    assert cliente.delete(f"{BASE}/portas/{porta}/conexao", headers=cab).json()["conexao"] is None
    assert cliente.get(f"{BASE}/bens/{pc_id}/portas", headers=c["cab"]["leitor"]).json() == []


def test_carga_pelo_inventario_lldp(cliente, admin):
    """Inventário LLDP: cria modelos, equipamentos (IP, função, status das portas com o nome real) e cabos; apaga os testes; rodar de novo não duplica."""
    from app.services.rede import importacao_lldp

    _cenario(cliente, admin)  # cria o SW-5A de teste
    inventario = {
        "excluir": ["SW-5A"],
        "equipamentos": [
            {"nome": "SPI-SWCORE-01", "tipo": "switch", "ip": "10.23.2.1", "funcao": "core_primario", "modelo": importacao_lldp.HUAWEI_S5755,
             "portas": {"MultiGE1/0/48": "up", "MultiGE1/0/47": "desativada", "25GE1/0/1": "down"}},
            {"nome": "SPI-SWDIST-01", "tipo": "switch", "ip": "10.23.2.2", "funcao": "distribuicao", "modelo": importacao_lldp.HUAWEI_S5755,
             "portas": {"MultiGE1/0/47": "up"}},
            {"nome": "SPI-01A-AP02", "tipo": "access_point", "ip": "10.23.6.18", "funcao": "acesso", "modelo": importacao_lldp.AIRENGINE, "portas": {}},
            {"nome": "SPI-SWAC-01A-DELL", "tipo": "switch", "ip": "10.23.1.19", "funcao": "acesso", "modelo": importacao_lldp.GENERICO_48,
             "fabricante": "Dell", "portas": {}},
        ],
        "ligacoes": [
            {"a": "SPI-SWCORE-01", "porta_a": "MultiGE1/0/48", "b": "SPI-SWDIST-01", "porta_b": "MultiGE1/0/47"},
            {"a": "SPI-SWDIST-01", "porta_a": "MultiGE1/0/1", "b": "SPI-01A-AP02", "porta_b": "MultiGE0/0/0"},
            {"a": "SPI-SWDIST-01", "porta_a": "MultiGE1/0/43", "b": "SPI-SWAC-01A-DELL", "porta_b": "Gi1/0/24"},
            {"a": "SPI-SWDIST-01", "porta_a": "MultiGE1/0/99", "b": "SPI-01A-AP02", "porta_b": "X"},
        ],
    }
    with FabricaSessao() as sessao:
        r = importacao_lldp.carregar(sessao, inventario)
        sessao.commit()
    c = r.contagem
    assert (c["excluido"], c["criado"], c["modelo_criado"], c["cabo_criado"]) == (1, 4, 3, 3), r.texto()
    assert len(r.avisos) == 1 and "MultiGE1/0/99" in r.avisos[0]
    with FabricaSessao() as sessao:
        core = sessao.scalar(select(EquipamentoRede).where(EquipamentoRede.nome == "SPI-SWCORE-01"))
        portas = {p.numero_logico: p for p in core.portas}
        assert len(portas) == 54 and (portas[48].nome, portas[48].status) == ("MultiGE1/0/48", "up")
        assert portas[47].status == "desativada" and (portas[49].nome, portas[49].status) == ("25GE1/0/1", "down")
        assert core.funcao == "core_primario" and core.ip_gerencia == "10.23.2.1"
        assert sessao.scalar(select(EquipamentoRede).where(EquipamentoRede.nome == "SW-5A")) is None
    t = cliente.get(f"{BASE}/topologia", headers=admin).json()
    assert [n["nome"] for n in t["raizes"]] == ["SPI-SWCORE-01"]
    dist = t["raizes"][0]["filhos"][0]
    assert dist["nome"] == "SPI-SWDIST-01" and sorted(f["nome"] for f in dist["filhos"]) == ["SPI-01A-AP02", "SPI-SWAC-01A-DELL"]
    # De novo: nada novo, cabos pulados
    with FabricaSessao() as sessao:
        r = importacao_lldp.carregar(sessao, inventario)
        sessao.commit()
    assert (r.contagem["criado"], r.contagem["atualizado"], r.contagem["cabo_existente"], r.contagem["cabo_criado"]) == (0, 4, 3, 0)


def test_porta_com_equipamento_fica_ligada(cliente, admin):
    """Ligar algo marca a porta como ligada; com algo ligado, não dá para desligar nem desativar: primeiro se retira o equipamento."""
    c = _cenario(cliente, admin)
    porta, cab = c["switch"]["portas"][2]["id"], c["cab"]["analista"]
    corpo = {"descricao": "Impressora", "modo": "access", "status": "down"}
    assert cliente.put(f"{BASE}/portas/{porta}", json=corpo, headers=cab).json()["status"] == "down"
    assert cliente.post(f"{BASE}/portas/{porta}/conexao", json={"descricao": "Impressora da recepção"}, headers=cab).status_code == 201
    assert cliente.get(f"{BASE}/portas/{porta}", headers=cab).json()["status"] == "up"
    for status in ("down", "desativada", None):
        r = cliente.put(f"{BASE}/portas/{porta}", json={**corpo, "status": status}, headers=cab)
        assert r.status_code == 409 and r.json()["codigo"] == "porta_com_equipamento"
    # Mudar o resto da configuração mantendo "ligada" continua valendo
    assert cliente.put(f"{BASE}/portas/{porta}", json={**corpo, "status": "up", "descricao": "Recepção"}, headers=cab).status_code == 200
    # Retirou o equipamento: aí pode desligar
    assert cliente.delete(f"{BASE}/portas/{porta}/conexao", headers=cab).status_code in (200, 204)
    assert cliente.put(f"{BASE}/portas/{porta}", json=corpo, headers=cab).json()["status"] == "down"
    # Ligação porta ↔ porta (salto): a porta já descrita como "Impressora" pede confirmação; confirmada, as duas pontas ficam ligadas
    # e ganham a descrição do salto
    outra = c["patch"]["portas"][0]["id"]
    r = cliente.post(f"{BASE}/portas/{porta}/conexao", json={"porta_id": outra}, headers=cab)
    assert r.status_code == 409 and r.json()["codigo"] == "porta_com_dispositivo"
    assert cliente.post(f"{BASE}/portas/{porta}/conexao", json={"porta_id": outra, "forcar": True}, headers=cab).status_code == 201
    lidas = {x: cliente.get(f"{BASE}/portas/{x}", headers=cab).json() for x in (porta, outra)}
    assert {p["status"] for p in lidas.values()} == {"up"}
    assert (lidas[porta]["descricao"], lidas[outra]["descricao"]) == ("Salto: PP-5A · 1", "Salto: SW-5A · 3")


def test_salto_sem_descricao_anterior_liga_direto_e_descreve_as_pontas(cliente, admin):
    """Portas sem descrição (ou já com a do salto) ligam sem confirmação e ganham a descrição do salto."""
    c = _cenario(cliente, admin)
    cab = c["cab"]["analista"]
    porta, outra = c["switch"]["portas"][4]["id"], c["patch"]["portas"][2]["id"]
    assert cliente.post(f"{BASE}/portas/{porta}/conexao", json={"porta_id": outra}, headers=cab).status_code == 201
    assert cliente.get(f"{BASE}/portas/{porta}", headers=cab).json()["descricao"] == "Salto: PP-5A · 3"
    assert cliente.get(f"{BASE}/portas/{outra}", headers=cab).json()["descricao"] == "Salto: SW-5A · 5"


def test_caminho_da_porta_ate_o_core(cliente, admin):
    """Core → distribuição → acesso → patch panel → ponto, com o cabo de cada degrau; dispositivos em cascata no fim; porta de subida avisa."""
    c = _cenario(cliente, admin)
    modelo, cab = c["modelo"]["id"], c["cab"]["analista"]
    novo = lambda nome, ip, funcao: cliente.post(f"{BASE}/equipamentos", json={"nome": nome, "modelo_face_id": modelo, "ip_gerencia": ip, "funcao": funcao},
                                                 headers=admin).json()
    core, dist = novo("SW-CORE", "10.23.2.1", "core_primario"), novo("SW-DIST", "10.23.2.2", "distribuicao")
    sw, pp = c["switch"], c["patch"]
    porta = lambda e, n: e["portas"][n - 1]["id"]
    for a, b in ((porta(core, 1), porta(dist, 1)), (porta(dist, 2), porta(sw, 9)), (porta(sw, 7), porta(pp, 3))):
        assert cliente.post(f"{BASE}/portas/{a}/conexao", json={"porta_id": b}, headers=cab).status_code == 201
    cliente.post(f"{BASE}/pontos", json={"codigo": "5A-12", "porta_id": porta(pp, 3)}, headers=cab)
    assert cliente.post(f"{BASE}/portas/{porta(sw, 4)}/conexao", json={"descricao": "Telefone IP"}, headers=cab).status_code == 201
    cliente.post(f"{BASE}/portas/{porta(sw, 4)}/conexao/atras", json={"descricao": "Computador"}, headers=cab)

    r = cliente.get(f"{BASE}/portas/{porta(sw, 4)}/caminho", headers=c["cab"]["leitor"])
    assert r.status_code == 200, r.text
    x = r.json()
    assert [(e["nome"], e["cabo"]) for e in x["etapas"]] == [("SW-CORE", ""), ("SW-DIST", "1 ↔ 1"), ("SW-5A", "2 ↔ SFP 1")]
    assert x["etapas"][0]["funcao"] == "core_primario" and [d["texto"] for d in x["dispositivos"]] == ["Telefone IP", "Computador"]
    assert x["cabo_dispositivos"] == "4" and x["aviso"] == ""
    # Os quadradinhos: porta que sobe (entrada) e porta que desce (saída) de cada caixa, com a configuração completa
    nome = lambda porta_lida: porta_lida["nome"] if porta_lida else None
    assert [(nome(e["porta_entrada"]), nome(e["porta_saida"])) for e in x["etapas"]] == [(None, "1"), ("1", "2"), ("SFP 1", "4")]
    assert x["etapas"][2]["porta_saida"]["conexao"]["texto"] == "Telefone IP" and x["etapas"][2]["porta_saida"]["status"] == "up"
    # Da porta do patch panel e da porta do switch que vai a ele: o mesmo caminho, terminando no ponto
    for p in (porta(pp, 3), porta(sw, 7)):
        etapas = cliente.get(f"{BASE}/portas/{p}/caminho", headers=c["cab"]["leitor"]).json()["etapas"]
        assert [(e["tipo"], e["nome"]) for e in etapas][-3:] == [("equipamento", "SW-5A"), ("equipamento", "PP-5A"), ("ponto", "5A-12")]
        assert etapas[3]["cabo"] == "7 ↔ 3"
        assert (etapas[2]["porta_saida"]["nome"], etapas[3]["porta_entrada"]["nome"], etapas[3]["porta_saida"]["nome"]) == ("7", "3", "3")
    # A porta de subida do switch: o caminho para nele (a tela destaca o quadradinho dela)
    x = cliente.get(f"{BASE}/portas/{porta(sw, 9)}/caminho", headers=c["cab"]["leitor"]).json()
    assert x["aviso"] == "" and x["etapas"][-1]["nome"] == "SW-5A"
    assert x["etapas"][-1]["porta_entrada"]["nome"] == "SFP 1" and x["etapas"][-1]["porta_saida"] is None


def _corpo_equipamento(e: dict, **mudancas) -> dict:
    """Corpo do PUT do equipamento a partir da leitura dele, com as mudanças pedidas."""
    campos = ("nome", "tipo", "modelo_face_id", "bem_id", "localizacao_id", "rack_id", "posicao_u", "ip_gerencia", "numero_serie", "observacao", "ativo", "funcao")
    return {**{k: e.get(k) for k in campos}, **mudancas}


def test_modelo_de_face_e_tipo_travados_depois_de_criado(cliente, admin):
    """O modelo de face não muda depois de criado (exclui e cadastra de novo); a grade de um modelo em uso também não; a edição é auditada."""
    c = _cenario(cliente, admin)
    sw, url = c["switch"], f"{BASE}/equipamentos/{c['switch']['id']}"
    outro = cliente.post(f"{BASE}/modelos", json={"nome": "Switch 48", "linhas": 2, "colunas": 24, "numeracao": "coluna"}, headers=admin).json()
    r = cliente.put(url, json=_corpo_equipamento(sw, modelo_face_id=outro["id"]), headers=admin)
    assert (r.status_code, r.json()["codigo"]) == (409, "modelo_travado")
    # As portas ficam como estavam (nenhuma criada)
    assert len(cliente.get(url, headers=admin).json()["portas"]) == 10
    # Switch não vira patch panel
    r = cliente.put(url, json=_corpo_equipamento(sw, tipo="patch_panel"), headers=admin)
    assert (r.status_code, r.json()["codigo"]) == (409, "tipo_travado")
    # Os demais dados mudam, e a edição entra na auditoria
    r = cliente.put(url, json=_corpo_equipamento(sw, numero_serie="ABC123"), headers=admin)
    assert r.status_code == 200, r.text
    from app.core.banco import FabricaSessao
    from app.models.auditoria import RegistroAuditoria
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(RegistroAuditoria).where(RegistroAuditoria.acao == "rede.equipamento.alterar")) is not None
    # Modelo em uso: a grade não muda, o nome sim
    modelo = f"{BASE}/modelos/{c['modelo']['id']}"
    extras = c["modelo"]["portas_extras"]
    r = cliente.put(modelo, json={"nome": "Switch 8+2", "linhas": 2, "colunas": 6, "numeracao": "coluna", "portas_extras": []}, headers=admin)
    assert (r.status_code, r.json()["codigo"]) == (409, "modelo_em_uso")
    r = cliente.put(modelo, json={"nome": "Switch 8+2 (5º andar)", "linhas": 2, "colunas": 4, "numeracao": "coluna", "portas_extras": extras}, headers=admin)
    assert r.status_code == 200 and r.json()["nome"] == "Switch 8+2 (5º andar)"
    # Modelo sem uso continua editável
    assert cliente.put(f"{BASE}/modelos/{outro['id']}", json={"nome": "Switch 24", "linhas": 2, "colunas": 12, "numeracao": "coluna"}, headers=admin).status_code == 200


def test_porta_exige_descricao_e_patch_panel_nao_tem_parte_logica(cliente, admin):
    """Toda porta salva tem descrição; a porta de patch panel guarda só descrição e situação, sem apagar o que já estava gravado."""
    c = _cenario(cliente, admin)
    cab = c["cab"]["analista"]
    porta_sw = c["switch"]["portas"][0]["id"]
    r = cliente.put(f"{BASE}/portas/{porta_sw}", json={"descricao": "   ", "modo": "access"}, headers=cab)
    assert r.status_code == 400 and "descrição" in r.json()["detalhe"]
    porta_pp = c["patch"]["portas"][0]["id"]
    assert cliente.get(f"{BASE}/portas/{porta_pp}", headers=cab).json()["equipamento_tipo"] == "patch_panel"
    for corpo in ({"modo": "trunk"}, {"vlan_nativa_id": c["v10"]["id"]}, {"vlans_tag": [c["v20"]["id"]]}, {"velocidade_mbps": 1000}):
        r = cliente.put(f"{BASE}/portas/{porta_pp}", json={"descricao": "Sala 504", "modo": "access", **corpo}, headers=cab)
        assert r.status_code == 400 and "patch panel" in r.json()["detalhe"], corpo
    # VLAN gravada antes da regra fica onde está quando só a descrição muda
    from app.core.banco import FabricaSessao
    from app.models.rede import PortaRede
    with FabricaSessao() as sessao:
        sessao.get(PortaRede, uuid.UUID(porta_pp)).vlan_nativa_id = uuid.UUID(c["v10"]["id"])
        sessao.commit()
    r = cliente.put(f"{BASE}/portas/{porta_pp}", json={"descricao": "Sala 504", "modo": "access", "status": "down"}, headers=cab)
    assert r.status_code == 200, r.text
    assert (r.json()["descricao"], r.json()["status"], r.json()["vlan_nativa"]) == ("Sala 504", "down", 10)


def test_indicadores_portas_alteradas_e_ativas_sem_descricao(cliente, admin):
    """Qualquer alteração da porta (configurar, ligar — as duas pontas —, ponto) entra em "alteradas" com quem e quando; ligada sem descrição entra no outro."""
    c = _cenario(cliente, admin)
    cab = c["cab"]["analista"]
    sw, pp = c["switch"]["portas"], c["patch"]["portas"]
    assert cliente.get(f"{BASE}/indicadores", headers=c["cab"]["leitor"]).json() == {"portas_alteradas": 0, "portas_ativas_sem_descricao": 0}
    # Configurar a porta 1 (com descrição, desligada); ligar a 2 do switch na 1 do patch panel (as duas pontas mudam e ficam ligadas)
    assert cliente.put(f"{BASE}/portas/{sw[0]['id']}", json={"descricao": "Impressora", "modo": "access", "status": "down"}, headers=cab).status_code == 200
    assert cliente.post(f"{BASE}/portas/{sw[1]['id']}/conexao", json={"porta_id": pp[0]["id"]}, headers=cab).status_code == 201
    # Uma porta ligada pela carga (sem descrição) entra em "ativas sem descrição", sem alteração registrada
    with FabricaSessao() as sessao:
        sessao.get(PortaRede, uuid.UUID(sw[2]["id"])).status = "up"
        sessao.commit()
    # Ponto de rede ligado a uma porta também é alteração dela
    assert cliente.post(f"{BASE}/pontos", json={"codigo": "5A-01", "porta_id": pp[3]["id"]}, headers=cab).status_code == 201
    assert cliente.get(f"{BASE}/indicadores", headers=cab).json() == {"portas_alteradas": 4, "portas_ativas_sem_descricao": 1}
    alteradas = cliente.get(f"{BASE}/portas-alteradas", headers=cab).json()
    assert {(x["equipamento_nome"], x["numero_logico"]) for x in alteradas} == {("SW-5A", 1), ("SW-5A", 2), ("PP-5A", 1), ("PP-5A", 4)}
    assert all(x["alterado_por"] == "analista" or x["alterado_por"] for x in alteradas) and all(x["alterado_em"] for x in alteradas)
    ligada = next(x for x in alteradas if (x["equipamento_nome"], x["numero_logico"]) == ("SW-5A", 2))
    assert ligada["descricao"] == "Salto: PP-5A · 1"
    # A tela da porta mostra a mesma última alteração (quem e quando); porta nunca alterada vem sem
    porta = cliente.get(f"{BASE}/portas/{sw[1]['id']}", headers=cab).json()
    assert (porta["alterado_por"], porta["alterado_em"][:19]) == (ligada["alterado_por"], ligada["alterado_em"][:19])
    assert cliente.get(f"{BASE}/portas/{sw[5]['id']}", headers=cab).json()["alterado_por"] is None
    # O equipamento mostra a alteração mais recente entre as portas dele (e qual porta foi)
    equip = cliente.get(f"{BASE}/equipamentos/{c['switch']['id']}", headers=cab).json()
    mais_recente = max((x for x in alteradas if x["equipamento_nome"] == "SW-5A"), key=lambda x: x["alterado_em"])
    assert (equip["alterado_por"], equip["alterado_porta"]) == (mais_recente["alterado_por"], mais_recente["porta"])
    # Equipamento sem nenhuma porta alterada vem sem
    novo = cliente.post(f"{BASE}/equipamentos", json={"nome": "SW-6A", "modelo_face_id": c["modelo"]["id"], "ip_gerencia": "10.23.6.2", "funcao": "acesso"}, headers=admin).json()
    assert novo["alterado_por"] is None and novo["alterado_porta"] is None
    sem = cliente.get(f"{BASE}/portas-sem-descricao", headers=cab).json()
    assert [(x["equipamento_nome"], x["numero_logico"], x["alterado_por"], x["alterado_em"]) for x in sem] == [("SW-5A", 3, None, None)]
    # Desligar também conta (as duas pontas), e o leitor vê as listas
    assert cliente.delete(f"{BASE}/portas/{sw[1]['id']}/conexao", headers=cab).status_code in (200, 204)
    assert cliente.get(f"{BASE}/portas-alteradas", headers=c["cab"]["leitor"]).status_code == 200
    # Alteração com mais de 7 dias sai da conta
    from datetime import timedelta

    from app.core.banco import agora_utc
    from app.models.auditoria import RegistroAuditoria
    with FabricaSessao() as sessao:
        for r in sessao.scalars(select(RegistroAuditoria).where(RegistroAuditoria.alvo_id == pp[3]["id"])):
            r.ocorrido_em = agora_utc() - timedelta(days=8)
        sessao.commit()
    assert cliente.get(f"{BASE}/indicadores", headers=cab).json()["portas_alteradas"] == 3


def test_vlan_tem_cor_como_os_marcadores(cliente, admin):
    """A VLAN nasce com uma cor sorteada (1–11), troca pela paleta (0–11), mantém a cor quando ela não vem e só quem administra muda."""
    c = _cenario(cliente, admin)
    v10 = c["v10"]
    assert 1 <= v10["cor_indice"] <= 11
    url = f"{BASE}/vlans/{v10['id']}"
    assert cliente.put(url, json={"numero": 10, "nome": "Dados", "cor_indice": 0}, headers=admin).json()["cor_indice"] == 0
    # Renomear sem mandar a cor mantém a cor
    r = cliente.put(url, json={"numero": 10, "nome": "Dados corporativos"}, headers=admin).json()
    assert (r["nome"], r["cor_indice"]) == ("Dados corporativos", 0)
    assert cliente.put(url, json={"numero": 10, "nome": "Dados", "cor_indice": 12}, headers=admin).status_code == 422
    # A cor nova aparece para todos (é da VLAN, não da porta); quem só edita portas não muda a VLAN
    assert next(v for v in cliente.get(f"{BASE}/vlans", headers=c["cab"]["leitor"]).json() if v["id"] == v10["id"])["cor_indice"] == 0
    assert cliente.put(url, json={"numero": 10, "nome": "Dados", "cor_indice": 3}, headers=c["cab"]["analista"]).status_code == 403
