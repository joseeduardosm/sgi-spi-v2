# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a faixa "Reservado CGI" do Protocolo (liberar a partir de) e a criação de tipo e faixa numa só chamada.
"""Protocolo: números reservados a Coordenadoria de Gestão e Infraestrutura até "liberar a partir de"."""

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.setor import Setor
from app.models.usuario import Usuario
from tests.conftest import cabecalho, criar_usuario

URL = "/api/protocolo"


def _montar(cliente, admin):
    """Carla administra, Ana e Bruno operam; Saulo é da CGI (departamento) e só tem Modificação."""
    ids = {l: criar_usuario(l, nome_completo=f"{l.title()} Souza", email=f"{l}@sp.gov.br") for l in ("carla", "ana", "saulo")}
    with FabricaSessao() as sessao:
        sessao.add(Setor(nome="Coordenadoria de Gestão e Infraestrutura"))
        sessao.flush()
        sessao.get(Usuario, ids["saulo"]).departamento = "Coordenadoria de Gestão e Infraestrutura"
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


def test_so_a_cgi_usa_a_faixa_reservada_os_demais_comecam_no_ponto(cliente, admin):
    h = _montar(cliente, admin)
    seq = _tipo_com_reserva(cliente, h)
    grade = _grade(cliente, h, seq)
    assert [n["estado"] for n in grade["itens"][:4]] == ["reservado_cgi"] * 3 + ["livre"] and grade["reservados_cgi"] == 3 and grade["pode_usar_reserva_cgi"] is False
    # Ana (comum) começa no 4; não escolhe número
    r = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Teste"}, headers=h["ana"])
    assert r.status_code == 201 and r.json()["numero"] == 4
    reservado = next(n for n in grade["itens"] if n["numero"] == 2)
    assert cliente.post(f"{URL}/numeros/{reservado['id']}/reservar", json={"finalidade": "x"}, headers=h["ana"]).status_code == 403
    # Saulo (CGI) começa pela faixa reservada e também escolhe um número dela, mas não os fora da reserva
    assert _grade(cliente, h, seq, "saulo")["pode_usar_reserva_cgi"] is True
    r = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "CGI 1"}, headers=h["saulo"])
    assert r.json()["numero"] == 1
    assert cliente.post(f"{URL}/numeros/{reservado['id']}/reservar", json={"finalidade": "CGI 2"}, headers=h["saulo"]).status_code == 200
    fora = next(n for n in grade["itens"] if n["numero"] == 7)
    assert cliente.post(f"{URL}/numeros/{fora['id']}/reservar", json={"finalidade": "x"}, headers=h["saulo"]).status_code == 403
    # A administração NÃO consome a faixa reservada pelo "próximo": recebe a partir do ponto de liberação
    r = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Adm"}, headers=h["carla"])
    assert r.json()["numero"] >= seq["liberar_a_partir_de"]


def test_liberar_volta_a_reservado_cgi_e_elevar_o_ponto_exige_numeros_sem_reserva(cliente, admin):
    h = _montar(cliente, admin)
    seq = _tipo_com_reserva(cliente, h)
    n = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "CGI"}, headers=h["saulo"]).json()
    assert n["numero"] == 1 and n["estado"] == "reservado"
    r = cliente.post(f"{URL}/numeros/{n['id']}/liberar", json={"motivo": "engano"}, headers=h["saulo"])
    assert r.status_code == 200 and r.json()["estado"] == "reservado_cgi"
    # Ana reserva o 4; elevar o ponto para 6 reservaria o 4 e 5 à CGI: recusa por causa do 4
    cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Ana"}, headers=h["ana"])
    r = cliente.put(f"{URL}/sequencias/{seq['id']}/faixa", json={"inicio": 1, "fim": 9, "liberar_a_partir_de": 6}, headers=h["carla"])
    assert r.status_code == 409
    # Baixar o ponto libera mais números; sem ponto, nada fica reservado
    assert cliente.put(f"{URL}/sequencias/{seq['id']}/faixa", json={"inicio": 1, "fim": 9, "liberar_a_partir_de": 2}, headers=h["carla"]).json()["liberar_a_partir_de"] == 2
    assert cliente.put(f"{URL}/sequencias/{seq['id']}/faixa", json={"inicio": 1, "fim": 9}, headers=h["carla"]).json()["liberar_a_partir_de"] is None
    assert _grade(cliente, h, seq)["reservados_cgi"] == 0


def test_fora_da_reserva_nao_consome_a_faixa_da_cgi_mesmo_para_quem_e_da_cgi(cliente, admin):
    """Usado por Contratos: a portaria sai depois do ponto de liberação, mesmo se quem solicita for da CGI."""
    from app.models.protocolo import SequenciaProtocolo
    from app.services import servico_protocolo

    h = _montar(cliente, admin)
    seq = _tipo_com_reserva(cliente, h)
    with FabricaSessao() as sessao:
        saulo = sessao.scalar(select(Usuario).where(Usuario.login == "saulo"))
        sequencia = sessao.get(SequenciaProtocolo, __import__("uuid").UUID(seq["id"]))
        assert servico_protocolo.proximo(sessao, sequencia.id, "Portaria", None, saulo, fora_da_reserva=True).numero == 4
        assert servico_protocolo.proximo(sessao, sequencia.id, "Outro", None, saulo).numero == 1


def test_concluir_sem_documento_de_documento_sigiloso(cliente, admin):
    h = _montar(cliente, admin)
    seq = _tipo_com_reserva(cliente, h, liberar=1)
    numero = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Portaria sigilosa"}, headers=h["ana"]).json()
    assert numero["pode_concluir_sem_documento"] is True
    assert cliente.post(f"{URL}/numeros/{numero['id']}/concluir-sem-documento", json={"motivo": "x"}, headers=h["saulo"]).status_code == 403
    assert cliente.put(f"{URL}/numeros/{numero['id']}/sigilo", json={"sigiloso": True}, headers=h["ana"]).status_code == 200
    r = cliente.post(f"{URL}/numeros/{numero['id']}/concluir-sem-documento", json={"motivo": "Documento sigiloso, fica com a chefia"}, headers=h["ana"])
    assert r.status_code == 200
    dados = r.json()
    assert dados["estado"] == "utilizado" and dados["arquivo"] is None and dados["usado_em"] and dados["pode_concluir_sem_documento"] is False
    assert [e["tipo"] for e in dados["eventos"]][-1] == "concluiu"
    assert cliente.post(f"{URL}/numeros/{numero['id']}/concluir-sem-documento", json={"motivo": "de novo"}, headers=h["ana"]).status_code == 409
    assert cliente.post(f"{URL}/numeros/{numero['id']}/liberar", json={"motivo": "x"}, headers=h["ana"]).status_code == 409


def test_concluir_sem_documento_exige_motivo(cliente, admin):
    h = _montar(cliente, admin)
    seq = _tipo_com_reserva(cliente, h, liberar=1)
    numero = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Portaria"}, headers=h["ana"]).json()
    assert cliente.post(f"{URL}/numeros/{numero['id']}/concluir-sem-documento", json={"motivo": "   "}, headers=h["ana"]).status_code == 400


def test_tipo_restrito_a_um_setor(cliente, admin):
    h = _montar(cliente, admin)
    # Saulo é da CGI (departamento); Ana não
    with FabricaSessao() as sessao:
        setor_id = sessao.scalar(select(Setor.id).where(Setor.nome == "Coordenadoria de Gestão e Infraestrutura"))
    r = cliente.post(f"{URL}/tipos", json={"nome": "Portaria SPI GC", "setor_id": setor_id, "sequencia": {"exercicio": 2026, "inicio": 1, "fim": 9}}, headers=h["carla"])
    assert r.status_code == 201 and r.json()["setor_id"] == setor_id and r.json()["setor_nome"] == "Coordenadoria de Gestão e Infraestrutura"
    seq = r.json()["sequencias"][0]
    assert cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Portaria"}, headers=h["ana"]).status_code == 403
    assert cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Portaria"}, headers=h["saulo"]).status_code == 201
    assert cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Portaria"}, headers=h["carla"]).status_code == 201
    tipos = {t["nome"]: t for t in cliente.get(f"{URL}/tipos", headers=h["saulo"]).json()["itens"]}
    assert tipos["Portaria SPI GC"]["pode_consumir"] is True
    assert "Portaria SPI GC" not in [t["nome"] for t in cliente.get(f"{URL}/tipos", headers=h["ana"]).json()["itens"]]
    assert cliente.get(f"{URL}/sequencias/{seq['id']}/numeros", headers=h["ana"]).status_code == 404
    # Sem setor, todos consomem
    livre = cliente.post(f"{URL}/tipos", json={"nome": "Ofício", "sequencia": {"exercicio": 2026, "inicio": 1, "fim": 9}}, headers=h["carla"]).json()
    assert livre["setor_id"] is None
    assert cliente.post(f"{URL}/sequencias/{livre['sequencias'][0]['id']}/proximo", json={"finalidade": "x"}, headers=h["ana"]).status_code == 201
    assert cliente.post(f"{URL}/tipos", json={"nome": "Outro", "setor_id": 999999}, headers=h["carla"]).status_code == 404


def test_tipo_restrito_so_o_setor_e_o_apoio_administrativo_veem(cliente, admin):
    h = _montar(cliente, admin)
    ids = {l: criar_usuario(l, nome_completo=f"{l.title()} Souza", email=f"{l}@sp.gov.br") for l in ("paulo", "sara")}
    with FabricaSessao() as sessao:
        setor_gc = Setor(nome="Gabinete GC")
        apoio = Setor(nome="Serviço de Apoio Administrativo")
        sessao.add_all([setor_gc, apoio])
        sessao.flush()
        sessao.get(Usuario, ids["paulo"]).departamento = "Gabinete GC"
        sessao.get(Usuario, ids["sara"]).departamento = "Serviço de Apoio Administrativo"
        sessao.commit()
        setor_id = setor_gc.id
    recurso = cliente.get("/api/acl/recursos", headers=admin).json()
    protocolo = next(r for r in (recurso["itens"] if isinstance(recurso, dict) else recurso) if r["slug"] == "protocolo")
    assert cliente.post("/api/acl/regras", json={"recurso_id": protocolo["id"], "nivel": "MODIFICACAO", "usuarios_ids": list(ids.values()), "setores_ids": []}, headers=admin).status_code == 201
    paulo, sara = cabecalho(cliente, "paulo"), cabecalho(cliente, "sara")
    r = cliente.post(f"{URL}/tipos", json={"nome": "Portaria SPI GC", "setor_id": setor_id, "sequencia": {"exercicio": 2026, "inicio": 1, "fim": 9}}, headers=h["carla"])
    seq = r.json()["sequencias"][0]
    assert cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Sigilosa"}, headers=paulo).status_code == 201

    def nomes(cab):
        return [t["nome"] for t in cliente.get(f"{URL}/tipos", headers=cab).json()["itens"]]

    assert "Portaria SPI GC" in nomes(paulo) and "Portaria SPI GC" in nomes(sara) and "Portaria SPI GC" in nomes(h["carla"])
    assert "Portaria SPI GC" not in nomes(h["ana"])
    assert cliente.get(f"{URL}/sequencias/{seq['id']}/numeros", headers=h["ana"]).status_code == 404
    assert cliente.get(f"{URL}/sequencias/{seq['id']}/numeros", headers=sara).status_code == 200
    # O apoio administrativo vê, mas não consome
    tipo_sara = next(t for t in cliente.get(f"{URL}/tipos", headers=sara).json()["itens"] if t["nome"] == "Portaria SPI GC")
    assert tipo_sara["pode_consumir"] is False
    assert cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "x"}, headers=sara).status_code == 403
    assert cliente.get(f"{URL}/exportar?tipo_id={tipo_sara['id']}", headers=h["ana"]).status_code == 404
