# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o Protocolo: próximo número, faixa por exercício, sigilo, liberar/anular, linha do tempo, painel e aviso.
"""Protocolo (`/api/protocolo`): numeração institucional por tipo e exercício."""

import io
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao, agora_utc
from app.models.mensagem import Mensagem
from app.models.protocolo import NumeroProtocolo
from app.services import servico_protocolo
from tests.apoio_contratos import PDF, criar_contrato
from tests.conftest import cabecalho, criar_usuario

URL = "/api/protocolo"


@pytest.fixture
def equipe(cliente, admin):
    """Ana e Bruno operam (MODIFICACAO), Carla administra (CONTROLE_TOTAL) e Dora só consulta (LEITURA)."""
    ids = {login: criar_usuario(login, nome_completo=f"{login.title()} Souza", email=f"{login}@sp.gov.br") for login in ("ana", "bruno", "carla", "dora", "fora")}
    recurso = cliente.post("/api/acl/recursos", json={"nome": "Protocolo", "slug": "protocolo"}, headers=admin).json()
    for nivel, logins in (("MODIFICACAO", ("ana", "bruno")), ("CONTROLE_TOTAL", ("carla",)), ("LEITURA", ("dora",))):
        r = cliente.post("/api/acl/regras", json={"recurso_id": recurso["id"], "nivel": nivel, "usuarios_ids": [ids[x] for x in logins], "setores_ids": []}, headers=admin)
        assert r.status_code == 201, r.text
    return ids, {login: cabecalho(cliente, login) for login in ids}


@pytest.fixture
def sequencia(cliente, equipe):
    """Tipo "Portaria" com a faixa 1 a 5 em 2026."""
    ids, h = equipe
    tipo = cliente.post(f"{URL}/tipos", json={"nome": "Portaria"}, headers=h["carla"]).json()
    seq = cliente.post(f"{URL}/tipos/{tipo['id']}/sequencias", json={"exercicio": 2026, "inicio": 1, "fim": 5}, headers=h["carla"])
    assert seq.status_code == 201, seq.text
    return tipo, seq.json()


def _proximo(cliente, h, seq, finalidade="Designar fiscal"):
    return cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": finalidade}, headers=h)


def test_acesso_por_nivel_do_recurso(cliente, equipe, sequencia):
    ids, h = equipe
    tipo, seq = sequencia
    # Quem não está nas regras não vê nada; leitura vê mas não reserva
    assert cliente.get(f"{URL}/tipos", headers=h["fora"]).status_code == 403
    assert cliente.get(f"{URL}/tipos", headers=h["dora"]).status_code == 200
    assert _proximo(cliente, h["dora"], seq).status_code == 403
    assert _proximo(cliente, h["ana"], seq).status_code == 201
    # Só CONTROLE_TOTAL cadastra tipos, cria faixas, lança número, anula
    assert cliente.post(f"{URL}/tipos", json={"nome": "Ofício"}, headers=h["ana"]).status_code == 403
    assert cliente.post(f"{URL}/tipos", json={"nome": "portaria"}, headers=h["carla"]).status_code == 409  # nome único sem diferenciar maiúsculas
    tipos = cliente.get(f"{URL}/tipos", headers=h["ana"]).json()
    assert tipos["pode_administrar"] is False and tipos["itens"][0]["sequencias"][0]["exercicio"] == 2026
    assert cliente.get(f"{URL}/tipos", headers=h["carla"]).json()["pode_administrar"] is True


def test_proximo_numero_e_sequencial_e_esgota(cliente, equipe, sequencia):
    ids, h = equipe
    _, seq = sequencia
    numeros = [_proximo(cliente, h["ana" if i % 2 else "bruno"], seq, f"Finalidade {i}").json() for i in range(5)]
    assert [n["numero"] for n in numeros] == [1, 2, 3, 4, 5] and numeros[0]["numero_formatado"] == "001/2026"
    assert numeros[0]["estado"] == "reservado" and numeros[1]["reservado_por_nome"] == "Ana Souza"
    esgotada = _proximo(cliente, h["ana"], seq)
    assert esgotada.status_code == 409 and esgotada.json()["codigo"] == "sequencia_esgotada"
    assert _proximo(cliente, h["ana"], seq, "").status_code == 422


def test_so_controle_total_lanca_numero_especifico_e_amplia_a_faixa_nos_dois_sentidos(cliente, equipe, sequencia):
    ids, h = equipe
    _, seq = sequencia
    lista = cliente.get(f"{URL}/sequencias/{seq['id']}/numeros", headers=h["ana"]).json()
    n4 = next(n for n in lista["itens"] if n["numero"] == 4)
    assert cliente.post(f"{URL}/numeros/{n4['id']}/reservar", json={"finalidade": "Pulo"}, headers=h["ana"]).status_code == 403
    r = cliente.post(f"{URL}/numeros/{n4['id']}/reservar", json={"finalidade": "Número reservado pela administração"}, headers=h["carla"])
    assert r.status_code == 200 and r.json()["numero"] == 4 and r.json()["eventos"][0]["tipo"] == "lancou"
    assert cliente.post(f"{URL}/numeros/{n4['id']}/reservar", json={"finalidade": "De novo"}, headers=h["carla"]).status_code == 409
    # O próximo continua sendo o menor livre (1), ignorando o 4
    assert _proximo(cliente, h["ana"], seq).json()["numero"] == 1
    # Ampliar para trás (0) e para frente (8): só criam os números novos; só CONTROLE_TOTAL
    assert cliente.put(f"{URL}/sequencias/{seq['id']}/faixa", json={"inicio": 0, "fim": 8}, headers=h["ana"]).status_code == 403
    nova = cliente.put(f"{URL}/sequencias/{seq['id']}/faixa", json={"inicio": 0, "fim": 8}, headers=h["carla"]).json()
    assert (nova["inicio"], nova["fim"]) == (0, 8)
    lista = cliente.get(f"{URL}/sequencias/{seq['id']}/numeros", headers=h["ana"]).json()
    assert [n["numero"] for n in lista["itens"]] == list(range(0, 9)) and lista["livres"] == 7
    assert _proximo(cliente, h["ana"], seq).json()["numero"] == 0  # o 0, que veio da ampliação para trás, é o menor livre
    # Não dá para encolher e excluir número reservado; encolher pontas livres vale
    assert cliente.put(f"{URL}/sequencias/{seq['id']}/faixa", json={"inicio": 2, "fim": 8}, headers=h["carla"]).status_code == 409
    assert cliente.put(f"{URL}/sequencias/{seq['id']}/faixa", json={"inicio": 0, "fim": 6}, headers=h["carla"]).status_code == 200


def test_liberar_anular_e_linha_do_tempo(cliente, equipe, sequencia):
    ids, h = equipe
    _, seq = sequencia
    n = _proximo(cliente, h["ana"], seq).json()
    # Outro operador não libera a reserva alheia; o dono libera com motivo; o número volta a livre e o histórico permanece
    assert cliente.post(f"{URL}/numeros/{n['id']}/liberar", json={"motivo": "Não preciso"}, headers=h["bruno"]).status_code == 403
    assert cliente.post(f"{URL}/numeros/{n['id']}/liberar", json={"motivo": ""}, headers=h["ana"]).status_code == 422
    liberado = cliente.post(f"{URL}/numeros/{n['id']}/liberar", json={"motivo": "Reservei por engano"}, headers=h["ana"]).json()
    assert liberado["estado"] == "livre" and liberado["reservado_por_nome"] == ""
    # Bruno reserva o mesmo número; a linha do tempo mostra as duas reservas e a liberação
    de_novo = _proximo(cliente, h["bruno"], seq).json()
    assert de_novo["id"] == n["id"] and de_novo["numero"] == 1
    historico = cliente.get(f"{URL}/numeros/{n['id']}", headers=h["dora"]).json()["eventos"]
    assert [e["tipo"] for e in historico] == ["reservou", "liberou", "reservou"] and historico[1]["texto"] == "Reservei por engano"
    # Só CONTROLE_TOTAL anula, com motivo; o número anulado não volta ao sorteio
    assert cliente.post(f"{URL}/numeros/{n['id']}/anular", json={"motivo": "Erro de digitação"}, headers=h["bruno"]).status_code == 403
    anulado = cliente.post(f"{URL}/numeros/{n['id']}/anular", json={"motivo": "Erro de digitação"}, headers=h["carla"]).json()
    assert anulado["estado"] == "anulado" and anulado["motivo_anulacao"] == "Erro de digitação"
    assert _proximo(cliente, h["ana"], seq).json()["numero"] == 2


def test_anexo_torna_utilizado_um_documento_por_numero_e_so_o_dono_anexa(cliente, equipe, sequencia):
    ids, h = equipe
    _, seq = sequencia
    n = _proximo(cliente, h["ana"], seq).json()
    arquivo = {"arquivo": ("portaria.pdf", io.BytesIO(PDF), "application/pdf")}
    assert cliente.post(f"{URL}/numeros/{n['id']}/anexo", files={"arquivo": ("portaria.pdf", io.BytesIO(PDF), "application/pdf")}, headers=h["bruno"]).status_code == 403
    r = cliente.post(f"{URL}/numeros/{n['id']}/anexo", files=arquivo, headers=h["ana"])
    assert r.status_code == 200 and r.json()["estado"] == "utilizado" and r.json()["arquivo"]["nome"] == "portaria.pdf"
    assert cliente.post(f"{URL}/numeros/{n['id']}/anexo", files={"arquivo": ("outro.pdf", io.BytesIO(PDF), "application/pdf")}, headers=h["ana"]).status_code == 409
    # Utilizado não se libera; o PDF baixa para quem tem acesso
    assert cliente.post(f"{URL}/numeros/{n['id']}/liberar", json={"motivo": "x"}, headers=h["ana"]).status_code == 409
    baixado = cliente.get(f"{URL}/numeros/{n['id']}/anexo", headers=h["dora"])
    assert baixado.status_code == 200 and baixado.content[:5] == b"%PDF-"
    # Arquivo inválido é recusado
    n2 = _proximo(cliente, h["ana"], seq).json()
    ruim = cliente.post(f"{URL}/numeros/{n2['id']}/anexo", files={"arquivo": ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream")}, headers=h["ana"])
    assert ruim.status_code == 400


def test_documento_sigiloso_so_o_dono_e_o_superroot_veem_o_arquivo(cliente, admin, equipe, sequencia):
    ids, h = equipe
    _, seq = sequencia
    n = _proximo(cliente, h["ana"], seq, "Processo disciplinar").json()
    cliente.post(f"{URL}/numeros/{n['id']}/anexo", files={"arquivo": ("sigilo.pdf", io.BytesIO(PDF), "application/pdf")}, headers=h["ana"])
    # Só o dono (ou o SuperRoot) marca o sigilo
    assert cliente.put(f"{URL}/numeros/{n['id']}/sigilo", json={"sigiloso": True}, headers=h["bruno"]).status_code == 403
    assert cliente.put(f"{URL}/numeros/{n['id']}/sigilo", json={"sigiloso": True}, headers=h["ana"]).json()["sigiloso"] is True
    # Dono e SuperRoot baixam; os demais, inclusive a administração do Protocolo, recebem 403
    assert cliente.get(f"{URL}/numeros/{n['id']}/anexo", headers=h["ana"]).status_code == 200
    assert cliente.get(f"{URL}/numeros/{n['id']}/anexo", headers=admin).status_code == 200
    for quem in ("bruno", "carla", "dora"):
        r = cliente.get(f"{URL}/numeros/{n['id']}/anexo", headers=h[quem])
        assert r.status_code == 403 and r.json()["codigo"] == "documento_sigiloso"
    # Os dados e a linha do tempo seguem visíveis para quem tem acesso ao Protocolo; o arquivo vem como "não pode baixar"
    visto = cliente.get(f"{URL}/numeros/{n['id']}", headers=h["bruno"]).json()
    assert visto["finalidade"] == "Processo disciplinar" and [e["tipo"] for e in visto["eventos"]] == ["reservou", "anexou", "sigilo"]
    assert visto["arquivo"]["pode_baixar"] is False and visto["sigiloso"] is True
    assert cliente.get(f"{URL}/numeros/{n['id']}", headers=h["ana"]).json()["arquivo"]["pode_baixar"] is True
    # Remover o sigilo devolve o acesso
    cliente.put(f"{URL}/numeros/{n['id']}/sigilo", json={"sigiloso": False}, headers=h["ana"])
    assert cliente.get(f"{URL}/numeros/{n['id']}/anexo", headers=h["bruno"]).status_code == 200


def test_vinculo_com_contrato_painel_e_exportacao(cliente, admin, equipe, sequencia):
    ids, h = equipe
    tipo, seq = sequencia
    contrato = criar_contrato(cliente, admin)
    n = cliente.post(f"{URL}/sequencias/{seq['id']}/proximo", json={"finalidade": "Designar fiscal", "contrato_id": contrato["id"]}, headers=h["ana"]).json()
    # O vínculo exige acesso ao Módulo de Contratos; como o recurso de contratos não tem regras, o acesso é aberto nos testes
    assert n["contrato_id"] == contrato["id"] and n["contrato_numero"] == contrato["numero"]
    assert [x["id"] for x in cliente.get(f"{URL}/contratos/{contrato['id']}", headers=h["dora"]).json()] == [n["id"]]
    desvinculado = cliente.put(f"{URL}/numeros/{n['id']}/contrato", json={"contrato_id": None}, headers=h["ana"]).json()
    assert desvinculado["contrato_id"] is None
    # Painel: uma reserva sem documento no mês corrente; depois do anexo vira utilização
    ano = agora_utc().year
    painel = cliente.get(f"{URL}/painel", params={"tipo_id": tipo["id"], "ano": ano}, headers=h["dora"]).json()
    assert sum(m["reservados"] for m in painel["meses"]) == 1 and [p["quantidade"] for p in painel["mais_reservaram"]] == [1]
    assert painel["sem_documento"][0]["numero_formatado"] == "001/2026" and painel["sem_documento"][0]["reservado_por_nome"] == "Ana Souza"
    cliente.post(f"{URL}/numeros/{n['id']}/anexo", files={"arquivo": ("d.pdf", io.BytesIO(PDF), "application/pdf")}, headers=h["ana"])
    painel = cliente.get(f"{URL}/painel", params={"tipo_id": tipo["id"], "ano": ano}, headers=h["dora"]).json()
    assert sum(m["utilizados"] for m in painel["meses"]) == 1 and painel["sem_documento"] == []
    # Exportação: XLSX e PDF só com os números com movimento
    xlsx = cliente.get(f"{URL}/exportar", params={"formato": "xlsx"}, headers=h["dora"])
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK" and "protocolo-" in xlsx.headers["content-disposition"]
    assert cliente.get(f"{URL}/exportar", params={"formato": "pdf", "tipo_id": tipo["id"], "exercicio": 2026}, headers=h["dora"]).content[:5] == b"%PDF-"


def test_aviso_de_reserva_sem_documento_uma_vez_por_marco_e_encerra_ao_anexar(cliente, equipe, sequencia):
    ids, h = equipe
    _, seq = sequencia
    n = _proximo(cliente, h["ana"], seq).json()
    with FabricaSessao() as sessao:
        assert servico_protocolo.lembrar_reservas(sessao) == 0  # recém-reservado
        sessao.get(NumeroProtocolo, __import__("uuid").UUID(n["id"])).reservado_em = agora_utc() - timedelta(days=6)
        sessao.commit()
        assert servico_protocolo.lembrar_reservas(sessao) == 1
        assert servico_protocolo.lembrar_reservas(sessao) == 0  # mesmo marco: não repete
        assert sessao.scalars(select(Mensagem.assunto).where(Mensagem.chave.like(f"protocolo:{n['id']}:%"))).all() == ["Documento pendente no Protocolo: Portaria 001/2026"]
    pendentes = cliente.get("/api/mensagens", headers=h["ana"]).json()["itens"]
    assert pendentes and pendentes[0]["pendente"] is True
    # Ao anexar o documento, o aviso é encerrado (some das pendências)
    cliente.post(f"{URL}/numeros/{n['id']}/anexo", files={"arquivo": ("d.pdf", io.BytesIO(PDF), "application/pdf")}, headers=h["ana"])
    assert cliente.get("/api/mensagens/resumo", headers=h["ana"]).json()["pendentes"] == 0


def test_excluir_tipo_so_sem_movimento_e_sequencia_unica_por_exercicio(cliente, equipe, sequencia):
    ids, h = equipe
    tipo, seq = sequencia
    assert cliente.post(f"{URL}/tipos/{tipo['id']}/sequencias", json={"exercicio": 2026, "inicio": 1, "fim": 9}, headers=h["carla"]).status_code == 409
    assert cliente.post(f"{URL}/tipos/{tipo['id']}/sequencias", json={"exercicio": 2027, "inicio": 1, "fim": 9}, headers=h["carla"]).status_code == 201
    vazio = cliente.post(f"{URL}/tipos", json={"nome": "Resolução"}, headers=h["carla"]).json()
    assert cliente.delete(f"{URL}/tipos/{vazio['id']}", headers=h["carla"]).status_code == 204
    _proximo(cliente, h["ana"], seq)
    assert cliente.delete(f"{URL}/tipos/{tipo['id']}", headers=h["carla"]).status_code == 409
