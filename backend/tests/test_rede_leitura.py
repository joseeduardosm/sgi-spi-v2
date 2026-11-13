"""
===============================================================================
ARQUIVO: test_rede_leitura.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar a leitura dos equipamentos de rede por SSH: os leitores de cada
fabricante, o nome da interface → porta da face, e o fluxo da API (testar no
cadastro, ler, ligar vizinhos LLDP sozinho, resumo e aplicar).

RESUMO TÉCNICO:
Os leitores rodam sobre textos: as saídas reais do Huawei S5755
(tests/dados_rede/huawei_*.txt, coletadas do SPI-SWCORE-01) e exemplos de
Dell OS6, Cisco IOS e H3C Comware. Na API, `leitura_ssh.ler` é trocado por
uma função falsa (nenhum SSH de verdade nos testes).

FINALIDADE DE NEGÓCIO:
Garante que a carga só traz o que reconhece, que "não conseguiu" vira aviso
e que nada é gravado sem a pessoa escolher (menos as ligações LLDP, que a
regra manda ligar sozinho).

CONTEXTO NO SISTEMA:
app/services/rede/leitura_ssh.py e servico_leitura.py; rotas em
app/api/routes/rede.py.

===============================================================================
"""
from pathlib import Path

import pytest

from app.services.rede import leitura_ssh as L
from tests.test_rede import BASE, _cenario, _lig, _novo

DADOS = Path(__file__).parent / "dados_rede"
EXTRAS_S5755 = [{"numero": 49 + i, "rotulo": f"25GE1/0/{i + 1}"} for i in range(4)] + [{"numero": 53, "rotulo": "100GE1/0/1"}, {"numero": 54, "rotulo": "100GE1/0/2"}]


def _executar_huawei(comando: str) -> str:
    """As saídas reais do SPI-SWCORE-01; comando sem saída gravada responde como o switch responde a comando desconhecido."""
    arquivos = {"display version": "huawei_versao.txt", "display device esn": "huawei_serie.txt", "display port vlan": "huawei_port_vlan.txt",
                "display interface | include (current state|Speed|Duplex|Description)": "huawei_interfaces.txt",
                "display lldp neighbor brief": "huawei_lldp.txt", "display vlan": "huawei_vlan.txt"}
    if comando in arquivos:
        return (DADOS / arquivos[comando]).read_text()
    return "\n          ^\nError: Unrecognized command found at '^' position."


def test_huawei_real():
    r = L.ler_textos("vrp", _executar_huawei)
    assert (r.modelo, r.serie, r.versao.startswith("1.25.0.1")) == ("S5755-H48UM4Y2CZ", "4E25A0025242", True)
    assert r.avisos == [] and len(r.portas) == 54 and len(r.vlans) == 24 and (172, "REDE-VOIP") in r.vlans
    assert r.vizinhos == [{"interface_local": "MultiGE1/0/48", "vizinho_interface": "MultiGE1/0/47", "vizinho_nome": "SPI-SWDIST-01"}]
    p48 = next(p for p in r.portas if p.interface == "MultiGE1/0/48")
    assert (p48.link, p48.velocidade, p48.duplex, p48.descricao, p48.modo, p48.pvid) == (True, 2500, "full", "UPLINK SPI-SWDIST-01", "trunk", 1)
    assert 2468 in p48.vlans_tag and 1 not in p48.vlans_tag
    # "1-4094" vira "todas", sem listar 4094 números; membro de Eth-Trunk fica sem modo; interfaces lógicas não entram
    p100 = next(p for p in r.portas if p.interface == "100GE1/0/1")
    assert (p100.modo, p100.todas_vlans, p100.vlans_tag) == ("dinamico_desejavel", True, [])
    assert next(p for p in r.portas if p.interface == "MultiGE1/0/1").modo is None
    assert not any(L.eh_logica(p.interface) for p in r.portas)


def test_so_comandos_de_consulta_saem():
    enviados = []
    L.ler_textos("vrp", lambda c: enviados.append(c) or "")
    L.ler_textos("ios", lambda c: enviados.append(c) or "")
    assert enviados and all(c.split()[0] in ("display", "show") for c in enviados)
    with pytest.raises(ValueError):
        L._so_consulta("system-view")


def test_nada_reconhecido_vira_aviso():
    r = L.ler_textos("vrp", lambda c: "Error: Unrecognized command")
    assert r.portas == [] and r.modelo == "" and len(r.avisos) >= 4


DELL_VERSAO = """Machine Description............... Dell Networking Switch
System Model ID................... N2024P
Machine Type...................... Dell Networking N2024P
Serial Number..................... CN0ABCDE123
Software Version.................. 6.6.3.10
"""
DELL_STATUS = """Port       Description                    Duplex Speed   Neg  Link   Flow Control
                                                               State  Status
--------- ------------------------------ ------ ------- ---- ------ -----------
Gi1/0/1    IMPRESSORA                     Full   1000    Auto Up     Active
Gi1/0/2                                   N/A    Unknown Auto Down   Inactive
Te1/0/1    UPLINK SPI-SWDIST-01           Full   10000   Off  Up     Active
"""
DELL_CONFIG = """interface Gi1/0/1
description "IMPRESSORA"
switchport access vlan 2478
exit
!
interface Te1/0/1
description "UPLINK SPI-SWDIST-01"
switchport mode trunk
switchport trunk native vlan 2476
switchport trunk allowed vlan 172,2468-2470,2476
exit
"""
DELL_LLDP = """Interface RemID   Chassis ID          Port ID           System Name
--------- ------- ------------------- ----------------- -----------------
Te1/0/1   1       70:7B:E8:00:00:01   MultiGE1/0/10     SPI-SWDIST-01
"""


def test_dell_os6_de_exemplo():
    saidas = {"show version": DELL_VERSAO, "show interfaces status": DELL_STATUS, "show running-config": DELL_CONFIG,
              "show lldp remote-device all": DELL_LLDP, "show vlan": "VLAN   Name                             Ports          Type\n2478   IMPRESSORAS                      Gi1/0/1        Static\n"}
    r = L.ler_textos("ios", lambda c: saidas.get(c, "% Invalid input detected"))
    assert (r.modelo, r.serie) == ("N2024P", "CN0ABCDE123")
    portas = {p.interface: p for p in r.portas}
    gi1, te1 = portas["Gi1/0/1"], portas["Te1/0/1"]
    assert (gi1.link, gi1.velocidade, gi1.modo, gi1.pvid, gi1.descricao) == (True, 1000, "access", 2478, "IMPRESSORA")
    assert (te1.modo, te1.pvid, te1.vlans_tag) == ("trunk", 2476, [172, 2468, 2469, 2470])
    assert r.vizinhos[0]["vizinho_nome"] == "SPI-SWDIST-01" and (2478, "IMPRESSORAS") in r.vlans


CISCO_STATUS = """Port      Name               Status       Vlan       Duplex  Speed Type
Gi1/0/1   Sala 504           connected    10         a-full  a-1000 10/100/1000BaseTX
Gi1/0/2                      notconnect   1            auto   auto 10/100/1000BaseTX
"""
CISCO_CONFIG = """interface GigabitEthernet1/0/1
 description Sala 504
 switchport access vlan 10
 switchport mode access
!
interface GigabitEthernet1/0/2
 shutdown
!
"""


def test_cisco_ios_de_exemplo_com_nomes_longos_e_curtos():
    saidas = {"show version": "Cisco IOS Software, Version 15.2(4)E\ncisco WS-C2960X-48FPD-L (APM86XXX) processor\nProcessor board ID FOC1234X0YZ\n",
              "show interfaces status": CISCO_STATUS, "show running-config": CISCO_CONFIG}
    r = L.ler_textos("ios", lambda c: saidas.get(c, "% Invalid input detected"))
    assert r.modelo == "WS-C2960X-48FPD-L" and r.serie == "FOC1234X0YZ"
    portas = {L.chave_interface(p.interface): p for p in r.portas}
    # "Gi1/0/1" (status) e "GigabitEthernet1/0/1" (configuração) são a mesma porta
    assert len(r.portas) == 2 and (portas["gi1/0/1"].link, portas["gi1/0/1"].velocidade, portas["gi1/0/1"].modo, portas["gi1/0/1"].pvid) == (True, 1000, "access", 10)
    assert portas["gi1/0/2"].desligada_no_switch is True


def test_h3c_comware_pela_configuracao():
    config = """interface GigabitEthernet1/0/5
 port link-type hybrid
 port hybrid vlan 10 20 tagged
 port hybrid vlan 30 untagged
 port hybrid pvid vlan 30
#
interface Ten-GigabitEthernet1/0/49
 port link-type trunk
 port trunk permit vlan 1 10 to 12
#
"""
    r = L.ler_textos("vrp", lambda c: config if c == "display current-configuration" else "Error: Unrecognized command")
    portas = {L.chave_interface(p.interface): p for p in r.portas}
    g5 = portas["gi1/0/5"]
    assert (g5.modo, g5.pvid, g5.vlans_tag, g5.vlans_sem_tag) == ("hybrid", 30, [10, 20], [])
    assert portas["xge1/0/49"].vlans_tag == [1, 10, 11, 12]


def test_interface_vira_porta_da_face():
    assert L.porta_da_interface("MultiGE1/0/5", 2, 24, EXTRAS_S5755) == 5
    assert L.porta_da_interface("25GE1/0/2", 2, 24, EXTRAS_S5755) == 50
    assert L.porta_da_interface("100GE1/0/1", 2, 24, EXTRAS_S5755) == 53
    assert L.porta_da_interface("Eth-Trunk1", 2, 24, EXTRAS_S5755) is None
    assert L.porta_da_interface("Gi1/0/24", 2, 12, []) == 24 and L.porta_da_interface("Gi1/0/25", 2, 12, []) is None
    assert L.lista_vlans("300 to 301 2468-2470,10") == ([10, 300, 301, 2468, 2469, 2470], False)


# ---------------------------------------------------------------------------------------------
# API, com o leitor falso
# ---------------------------------------------------------------------------------------------

def _leitura_falsa(nome: str, vizinhos: list[dict], portas: list[L.PortaLida]) -> L.Leitura:
    return L.Leitura(tipo="huawei_vrpv8", nome=nome, modelo="S-FALSO", serie="SERIE-123", versao="1.0", portas=portas,
                     vlans=[(10, "Dados"), (20, "Voz"), (777, "NOVA")], vizinhos=vizinhos)


def test_leitura_desativada_por_enquanto(cliente, admin):
    """Com a chave desligada (decisão do usuário), a leitura é recusada e nada entra no equipamento."""
    from app.services.rede import servico_leitura
    assert servico_leitura.LEITURA_SSH_ATIVA is False
    r = cliente.post(f"{BASE}/leitura/testar", json={"ip": "10.0.0.6", "usuario": "u", "senha": "s"}, headers=admin)
    assert (r.status_code, r.json()["codigo"]) == (409, "leitura_desativada")


def test_testar_ler_ligar_lldp_e_aplicar(cliente, admin, monkeypatch):
    from app.services.rede import servico_leitura
    monkeypatch.setattr(servico_leitura, "LEITURA_SSH_ATIVA", True)
    c = _cenario(cliente, admin)
    m = c["modelo"]["id"]
    chamadas = []

    def falso(ip, usuario, senha, porta=22, tipo=None):
        chamadas.append((ip, usuario, senha, tipo))
        if senha == "errada":
            raise L.ErroLeitura("Usuário ou senha recusados pelo equipamento.")
        portas = [L.PortaLida("SFP1", link=True, velocidade=10000, duplex="full", modo="trunk", pvid=10, vlans_tag=[20]),
                  L.PortaLida("Gi1/0/3", link=True, velocidade=1000, duplex="full", descricao="IMPRESSORA 5A", modo="access", pvid=10),
                  L.PortaLida("Gi1/0/4", link=False, descricao="", modo="access", pvid=10)]
        return _leitura_falsa("SW-6A", [{"interface_local": "SFP1", "vizinho_nome": "SW-DIST", "vizinho_interface": "2"}], portas)
    monkeypatch.setattr(L, "ler", falso)
    # O modelo de teste chama a porta 9 de "SFP 1": a interface lida "SFP1" é a mesma (sem espaço)
    corpo = {"ip": "10.0.0.6", "usuario": "leitor", "senha": "x", "modelo_face_id": m, "tipo": "switch", "funcao": "acesso"}
    r = cliente.post(f"{BASE}/leitura/testar", json=corpo, headers=admin)
    assert r.status_code == 200, r.text
    sug = r.json()["sugestao"]
    assert (r.json()["nome"], sug["porta_numero"], sug["destino_porta_id"]) == ("SW-6A", 9, c["dist"]["portas"][1]["id"])
    assert cliente.post(f"{BASE}/leitura/testar", json={**corpo, "senha": "errada"}, headers=admin).json()["codigo"] == "leitura_falhou"
    assert cliente.post(f"{BASE}/leitura/testar", json=corpo, headers=c["cab"]["analista"]).status_code == 403

    # Cadastra com o acesso; a senha nunca volta
    novo = _novo(cliente, admin, "SW-6A", m, "acesso", ligacao=_lig(10, c["dist"]["portas"][2]["id"]))
    eid = novo.json()["id"]
    campos = ("nome", "tipo", "modelo_face_id", "bem_id", "localizacao_id", "rack_id", "posicao_u", "ip_gerencia", "numero_serie", "observacao", "ativo", "funcao")
    base = {k: novo.json()[k] for k in campos}
    r = cliente.put(f"{BASE}/equipamentos/{eid}", json={**base, "acesso_usuario": "leitor", "acesso_senha": "s3cr3ta"}, headers=admin)
    assert r.status_code == 200 and r.json()["tem_acesso"] is True and "acesso_senha" not in r.json() and "s3cr3ta" not in r.text
    # Sem mandar a senha de novo, ela fica
    assert cliente.put(f"{BASE}/equipamentos/{eid}", json={**base, "acesso_usuario": "leitor"}, headers=admin).json()["tem_acesso"] is True

    r = cliente.post(f"{BASE}/equipamentos/{eid}/leitura", headers=admin)
    assert r.status_code == 201, r.text
    assert chamadas[-1][2] == "s3cr3ta"  # a senha decifrada chegou ao leitor
    res = r.json()
    # LLDP: a SFP1 (porta 9) do SW-6A ligou sozinha na porta 2 do SW-DIST
    assert res["lldp"][0]["situacao"] == "ligada"
    face = cliente.get(f"{BASE}/equipamentos/{eid}", headers=admin).json()
    assert face["portas"][8]["conexao"]["texto"] == "SW-DIST · porta 2" and face["leitura_em"]
    # Resumo: série, VLAN nova (777), porta com descrição sem ligação (Gi1/0/3 = porta 3) e configurações
    assert res["equipamento"]["serie_lida"] == "SERIE-123" and [v["numero"] for v in res["vlans_novas"]] == [777]
    assert [d["interface"] for d in res["descricoes"]] == ["Gi1/0/3"]
    assert {x["interface"] for x in res["configuracao"]} >= {"SFP1", "Gi1/0/3"}
    # Nada além do LLDP foi gravado ainda
    assert cliente.get(f"{BASE}/equipamentos/{eid}", headers=admin).json()["numero_serie"] == ""

    escolhas = {"equipamento": True, "vlans": [777], "descricoes": ["Gi1/0/3"], "configuracao": ["SFP1", "Gi1/0/3", "Gi1/0/4"]}
    r = cliente.post(f"{BASE}/equipamentos/{eid}/leitura/aplicar", json=escolhas, headers=admin)
    assert r.status_code == 200, r.text
    portas = {p["numero_logico"]: p for p in r.json()["portas"]}
    assert r.json()["numero_serie"] == "SERIE-123"
    assert (portas[3]["descricao"], portas[3]["modo"], portas[3]["vlan_nativa"], portas[3]["status"]) == ("IMPRESSORA 5A", "access", 10, "up")
    assert (portas[9]["modo"], portas[9]["vlan_nativa"], portas[9]["vlans_tag"], portas[9]["velocidade_mbps"]) == ("trunk", 10, [20], 10000)
    # Porta 4 continua sem ligação: a configuração não se aplica (regra do SGI)
    assert (portas[4]["status"], portas[4]["descricao"]) == ("down", "Desligado")
    assert 777 in [v["numero"] for v in cliente.get(f"{BASE}/vlans", headers=admin).json()]
    assert cliente.get(f"{BASE}/equipamentos/{eid}/leitura", headers=c["cab"]["leitor"]).json()["aplicada_em"]


def test_ler_sem_acesso_gravado(cliente, admin, monkeypatch):
    from app.services.rede import servico_leitura
    monkeypatch.setattr(servico_leitura, "LEITURA_SSH_ATIVA", True)
    c = _cenario(cliente, admin)
    r = cliente.post(f"{BASE}/equipamentos/{c['switch']['id']}/leitura", headers=admin)
    assert (r.status_code, r.json()["codigo"]) == (400, "sem_acesso")
    assert cliente.get(f"{BASE}/equipamentos/{c['switch']['id']}/leitura", headers=admin).json() is None
