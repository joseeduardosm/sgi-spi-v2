# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a faixa "Reservado SAA" do Protocolo (liberar a partir de) e a criação de tipo e faixa numa só chamada.
"""Protocolo: números reservados ao Serviço de Apoio Administrativo até "liberar a partir de"."""

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.setor import Setor
from app.models.usuario import Usuario
from tests.conftest import cabecalho, criar_usuario

URL = "/api/protocolo"


def _montar(cliente, admin):
    """Carla administra, Ana e Bruno operam; Saulo é do SAA (departamento) e só tem Modificação."""
    ids = {l: criar_usuario(l, nome_completo=f"{l.title()} Souza", email=f"{l}@sp.gov.br") for l in ("carla", "ana", "saulo")}
    with FabricaSessao() as sessao:
        sessao.add(Setor(nome="Serviço de Apoio Administrativo"))
        sessao.flush()
        sessao.get(Usuario, ids["saulo"]).departamento = "Serviço de Apoio Administrativo"
        sessao.commit()
    recurso = cliente.post("/api/acl/recursos", json={"nome": "Protocolo", "slug": "protocolo"}, headers=admin).json()
    for nivel, logins in (("MODIFICACAO", ("ana", "saulo")), ("CONTROLE_TOTAL", ("carla",))):
        assert cliente.post("/api/acl/regras", json={"recurso_id": recurso["id"], "nivel": nivel, "usuarios_ids": [ids[x] for x in logins], "setores_ids": []}, headers=admin).status_code == 201
    return {l: cabecalho(cliente, l) for l in ids}


def _tipo_com_reserva(cliente, h, liberar=4):
    r = cliente.post(f"{URL}/tipos", json={"nome": "Portaria SPI SSGC", "sequencia": {"exercicio": 2026, "inicio": 1, "fim": 9, "liberar_a_partir_de": liberar}}, headers=h["carla"])
    assert r.status_code == 201, r.text
    return r.json()["sequencias"][0]


def _grade(cliente, h, seq, quem="ana"):
    return cliente.get(f"{URL}/sequencias/{seq['id']}/numeros", headers=h[quem]).json()


def test_criacao_atomica_de_tipo_e_faixa_e_validacao_do_ponto(cliente, admin):
    h = _montar(cliente, admin)
    seq = _tipo_com_reserva(cliente, h)
    assert (seq["inicio"], seq["fim"], seq["liberar_a_partir_de"]) == (1, 9, 4)
    # Fora da faixa: recusa e não deixa tipo pela metade
    r = cliente.post(f"{URL}/tipos", json={"nome": "Ofício", "sequencia": {"exercicio": 2026, "inicio": 1, "fim": 9, "liberar_a_partir_de": 50}}, headers=h["carla"])
    assert r.status_code == 400
    assert "Ofício" not in [t["nome"] for t in cliente.get(f"{URL}/tipos", headers=h["carla"]).json()["itens"]]


def test_so_o_saa_usa_a_faixa_reservada_os_demais_comecam_no_ponto(cliente, admin):
    h = _montar(cliente, admin)
    seq = _tipo_com_reserva(cliente, h)
    grade = _grade(cliente, h, seq)
    assert [n["estado"] for n in grade["itens"][:4]] == ["reservado_saa"] * 3 + ["livre"] and grade["reservados_saa"] == 3 and grade["pode_usar_reserva_saa"] is False
    # Ana (comum) começa no 4; não escolhe número
    r = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Teste"}, headers=h["ana"])
    assert r.status_code == 201 and r.json()["numero"] == 4
    reservado = next(n for n in grade["itens"] if n["numero"] == 2)
    assert cliente.post(f"{URL}/numeros/{reservado['id']}/reservar", json={"finalidade": "x"}, headers=h["ana"]).status_code == 403
    # Saulo (SAA) começa pela faixa reservada e também escolhe um número dela, mas não os fora da reserva
    assert _grade(cliente, h, seq, "saulo")["pode_usar_reserva_saa"] is True
    r = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "SAA 1"}, headers=h["saulo"])
    assert r.json()["numero"] == 1
    assert cliente.post(f"{URL}/numeros/{reservado['id']}/reservar", json={"finalidade": "SAA 2"}, headers=h["saulo"]).status_code == 200
    fora = next(n for n in grade["itens"] if n["numero"] == 7)
    assert cliente.post(f"{URL}/numeros/{fora['id']}/reservar", json={"finalidade": "x"}, headers=h["saulo"]).status_code == 403
    # A administração NÃO consome a faixa reservada pelo "próximo": recebe a partir do ponto de liberação
    r = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Adm"}, headers=h["carla"])
    assert r.json()["numero"] >= seq["liberar_a_partir_de"]


def test_liberar_volta_a_reservado_saa_e_elevar_o_ponto_exige_numeros_sem_reserva(cliente, admin):
    h = _montar(cliente, admin)
    seq = _tipo_com_reserva(cliente, h)
    n = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "SAA"}, headers=h["saulo"]).json()
    assert n["numero"] == 1 and n["estado"] == "reservado"
    r = cliente.post(f"{URL}/numeros/{n['id']}/liberar", json={"motivo": "engano"}, headers=h["saulo"])
    assert r.status_code == 200 and r.json()["estado"] == "reservado_saa"
    # Ana reserva o 4; elevar o ponto para 6 reservaria o 4 e 5 ao SAA: recusa por causa do 4
    cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Ana"}, headers=h["ana"])
    r = cliente.put(f"{URL}/sequencias/{seq['id']}/faixa", json={"inicio": 1, "fim": 9, "liberar_a_partir_de": 6}, headers=h["carla"])
    assert r.status_code == 409
    # Baixar o ponto libera mais números; sem ponto, nada fica reservado
    assert cliente.put(f"{URL}/sequencias/{seq['id']}/faixa", json={"inicio": 1, "fim": 9, "liberar_a_partir_de": 2}, headers=h["carla"]).json()["liberar_a_partir_de"] == 2
    assert cliente.put(f"{URL}/sequencias/{seq['id']}/faixa", json={"inicio": 1, "fim": 9}, headers=h["carla"]).json()["liberar_a_partir_de"] is None
    assert _grade(cliente, h, seq)["reservados_saa"] == 0


def test_fora_da_reserva_nao_consome_a_faixa_do_saa_mesmo_para_quem_e_do_saa(cliente, admin):
    """Usado por Contratos: a portaria sai depois do ponto de liberação, mesmo se quem solicita for do SAA."""
    from app.models.protocolo import SequenciaProtocolo
    from app.services import servico_protocolo

    h = _montar(cliente, admin)
    seq = _tipo_com_reserva(cliente, h)
    with FabricaSessao() as sessao:
        saulo = sessao.scalar(select(Usuario).where(Usuario.login == "saulo"))
        sequencia = sessao.get(SequenciaProtocolo, __import__("uuid").UUID(seq["id"]))
        assert servico_protocolo.proximo(sessao, sequencia.id, "Portaria", None, saulo, fora_da_reserva=True).numero == 4
        assert servico_protocolo.proximo(sessao, sequencia.id, "Outro", None, saulo).numero == 1
