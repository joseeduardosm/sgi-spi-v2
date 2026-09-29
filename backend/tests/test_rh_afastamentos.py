# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar férias e licença-prêmio (Módulo RH, funcionalidade 2).
"""Férias e licença-prêmio: regras parametrizáveis, aprovação (autorizador, substituto, CGP), painel e exportação."""

from datetime import date

import pytest

from app.core.banco import FabricaSessao
from app.models.rh import Afastamento
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.services.rh import servico_afastamentos
from app.tarefas import mensageria
from tests.apoio_rh import criar_cgp, funcionais, simular_smtp
from tests.conftest import cabecalho, criar_usuario
from tests.test_smtp import SmtpSimulado, dados_servidor

URL = "/api/rh/afastamentos"
HOJE = date(2026, 10, 1)  # quinta-feira


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    simular_smtp(monkeypatch)
    monkeypatch.setattr("app.services.rh.servico_afastamentos.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: HOJE)


@pytest.fixture
def equipe(cliente, admin):
    """Chefe autoriza Ana e Bia (Diretoria A, com a Coordenadoria A1 filha); Rita é da CGP; Sílvia substitui o chefe."""
    ids = {login: criar_usuario(login, nome_completo=nome, email=f"{login}@sp.gov.br", departamento=depto) for login, nome, depto in (
        ("chefe", "Chefe Silva", "Diretoria A"), ("ana", "Ana Souza", "Diretoria A"), ("bia", "Bia Lima", "Coordenadoria A1"),
        ("rh", "Rita RH", "Coordenadoria de Gestão de Pessoas"), ("sub", "Sílvia Substituta", "Diretoria A"))}
    criar_cgp()
    with FabricaSessao() as sessao:
        diretoria = Setor(nome="Diretoria A")
        sessao.add(diretoria)
        sessao.flush()
        sessao.add(Setor(nome="Coordenadoria A1", setor_pai_id=diretoria.id))
        sessao.commit()
        diretoria_id = diretoria.id
    for pessoa in ("ana", "bia"):
        funcionais(ids[pessoa], autorizador_id=ids["chefe"], exercicio=2026, inicio_aquisitivo_dia=1, inicio_aquisitivo_mes=1, saldo_lp_dias=10)
    funcionais(ids["chefe"], autorizador_id=ids["rh"], substituto_id=ids["sub"], exercicio=2026, inicio_aquisitivo_dia=1, inicio_aquisitivo_mes=1,
               saldo_lp_dias=0)
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    return ids, {k: cabecalho(cliente, k) for k in ids}, diretoria_id


def _pedir(cliente, h, inicio, fim, tipo="ferias"):
    return cliente.post(URL, json={"tipo": tipo, "inicio": inicio, "fim": fim}, headers=h)


def test_regras_de_agendamento(cliente, equipe):
    ids, h, _ = equipe
    erro = lambda r: (r.status_code, r.json()["detalhe"])  # noqa: E731
    assert "pelo menos 5 dias" in erro(_pedir(cliente, h["ana"], "2026-11-03", "2026-11-05"))[1]
    assert "segunda-feira" in erro(_pedir(cliente, h["ana"], "2026-11-02", "2026-11-10"))[1]
    assert "antecedência" in erro(_pedir(cliente, h["ana"], "2026-10-13", "2026-10-20"))[1]
    assert "exercício" in erro(_pedir(cliente, h["ana"], "2026-12-29", "2027-01-05", "licenca_premio"))[1]
    assert "Saldo de licença-prêmio insuficiente: 10 dia(s)" in erro(_pedir(cliente, h["ana"], "2026-11-03", "2026-11-14", "licenca_premio"))[1]
    assert _pedir(cliente, h["ana"], "2026-11-03", "2026-11-12").status_code == 201
    assert "sobrepõe" in erro(_pedir(cliente, h["ana"], "2026-11-10", "2026-11-16", "licenca_premio"))[1]
    # Saldos independentes: licença-prêmio emendada logo depois das férias (permitido por padrão)
    assert _pedir(cliente, h["ana"], "2026-11-13", "2026-11-17", "licenca_premio").status_code == 201
    meus = cliente.get(f"{URL}/meus", headers=h["ana"]).json()
    assert meus["saldos"]["ferias"] == {"saldo": 30, "usado": 10, "disponivel": 20} and meus["saldos"]["licenca_premio"]["disponivel"] == 5
    # A CGP muda as regras: proíbe emenda e libera segunda-feira
    parametros = {**cliente.get("/api/rh/parametros", headers=h["ana"]).json(), "permite_emenda": False, "inicio_vedado_ferias": []}
    parametros = {k: v for k, v in parametros.items() if k not in ("atualizado_por_nome", "atualizado_em")}
    assert cliente.put("/api/rh/parametros", json=parametros, headers=h["ana"]).status_code == 403
    assert cliente.put("/api/rh/parametros", json=parametros, headers=h["rh"]).status_code == 200
    assert "emendar" in erro(_pedir(cliente, h["ana"], "2026-11-18", "2026-11-22"))[1]
    assert _pedir(cliente, h["ana"], "2026-11-23", "2026-11-27").status_code == 201  # segunda-feira liberada


def test_aprovacao_alteracao_cancelamento_e_emails(cliente, equipe, monkeypatch):
    ids, h, _ = equipe
    SmtpSimulado.enviadas.clear()
    pedido = _pedir(cliente, h["ana"], "2026-11-03", "2026-11-12").json()
    with FabricaSessao() as sessao:
        mensageria.enviar_emails_pendentes(sessao)
    assert sorted(para[0] for _, _, para, _ in SmtpSimulado.enviadas) == ["chefe@sp.gov.br", "rh@sp.gov.br"]
    assert SmtpSimulado.enviadas[0][0]["Subject"] == "Ana Souza agendou férias e aguarda aprovação"
    # Bia não decide; a própria Ana não decide; o chefe decide
    assert cliente.post(f"{URL}/{pedido['id']}/aprovar", headers=h["bia"]).status_code == 403
    assert cliente.post(f"{URL}/{pedido['id']}/recusar", json={"justificativa": ""}, headers=h["chefe"]).status_code == 400
    assert [p["id"] for p in cliente.get(f"{URL}/aprovacoes", headers=h["chefe"]).json()] == [pedido["id"]]
    aprovado = cliente.post(f"{URL}/{pedido['id']}/aprovar", headers=h["chefe"]).json()
    assert aprovado["status"] == "aprovado" and aprovado["decidido_por_nome"] == "Chefe Silva"
    # Alterar um aprovado cria um novo pedido; ao aprovar, o anterior é cancelado
    novo = cliente.put(f"{URL}/{pedido['id']}", json={"tipo": "ferias", "inicio": "2026-11-10", "fim": "2026-11-19"}, headers=h["ana"]).json()
    assert novo["status"] == "pendente" and novo["substitui_id"] == pedido["id"]
    cliente.post(f"{URL}/{novo['id']}/aprovar", headers=h["rh"])
    estados = {a["id"]: a["status"] for a in cliente.get(f"{URL}/meus", headers=h["ana"]).json()["afastamentos"]}
    assert estados == {pedido["id"]: "cancelado", novo["id"]: "aprovado"}
    # Fora do prazo (menos de 5 dias do início) o usuário não cancela; a CGP cancela
    monkeypatch.setattr("app.services.rh.servico_afastamentos.hoje", lambda: date(2026, 11, 7))
    r = cliente.post(f"{URL}/{novo['id']}/cancelar", json={}, headers=h["ana"])
    assert r.status_code == 400 and "prazo" in r.json()["detalhe"]
    assert cliente.post(f"{URL}/{novo['id']}/cancelar", json={"justificativa": "Pedido da chefia"}, headers=h["rh"]).json()["status"] == "cancelado"
    # O usuário recebeu e-mail a cada mudança de status
    SmtpSimulado.enviadas.clear()
    with FabricaSessao() as sessao:
        mensageria.enviar_emails_pendentes(sessao)
    assuntos = [m["Subject"] for m, _, para, _ in SmtpSimulado.enviadas if para == ["ana@sp.gov.br"]]
    assert assuntos.count("Férias aprovada(s)") == 2 and "Afastamento cancelado: férias" in assuntos


def test_substituto_decide_com_o_autorizador_afastado(cliente, equipe, monkeypatch):
    ids, h, _ = equipe
    pedido = _pedir(cliente, h["ana"], "2026-11-24", "2026-12-03").json()
    with FabricaSessao() as sessao:
        sessao.add(Afastamento(usuario_id=ids["chefe"], tipo="ferias", inicio=date(2026, 11, 3), fim=date(2026, 11, 20), dias=18,
                               exercicio=2026, status="aprovado"))
        sessao.commit()
    monkeypatch.setattr("app.services.rh.servico_afastamentos.hoje", lambda: date(2026, 11, 10))
    assert cliente.post(f"{URL}/{pedido['id']}/aprovar", headers=h["chefe"]).status_code == 403
    assert cliente.get("/api/rh/papeis", headers=h["sub"]).json()["autorizador"] is True
    assert cliente.post(f"{URL}/{pedido['id']}/aprovar", headers=h["sub"]).json()["status"] == "aprovado"
    # Depois do fim, a tarefa diária marca como gozado
    with FabricaSessao() as sessao:
        assert servico_afastamentos.marcar_gozados(sessao, date(2026, 12, 4)) == 2


def test_painel_escopo_setor_alerta_e_exportacao(cliente, equipe):
    ids, h, diretoria = equipe
    for pessoa in ("ana", "bia"):
        pedido = _pedir(cliente, h[pessoa], "2026-11-03", "2026-11-12").json()
        cliente.post(f"{URL}/{pedido['id']}/aprovar", headers=h["chefe"])
    _pedir(cliente, h["chefe"], "2026-11-10", "2026-11-16")
    params = {"visao": "mensal", "ano": 2026, "mes": 11}
    # CGP vê todos; o chefe vê os autorizados e a si mesmo; a Ana só a si
    assert len(cliente.get(f"{URL}/painel", params=params, headers=h["rh"]).json()["periodos"]) == 3
    chefe = cliente.get(f"{URL}/painel", params=params, headers=h["chefe"]).json()
    assert {p["nome"] for p in chefe["periodos"]} == {"Ana Souza", "Bia Lima", "Chefe Silva"}
    assert {p["nome"] for p in cliente.get(f"{URL}/painel", params=params, headers=h["ana"]).json()["periodos"]} == {"Ana Souza"}
    # Setor com filhos: Diretoria A inclui a Coordenadoria A1 (Bia)
    filtro = cliente.get(f"{URL}/painel", params={**params, "setor_id": diretoria, "tipo": "ferias"}, headers=h["rh"]).json()
    assert {p["nome"] for p in filtro["periodos"]} == {"Ana Souza", "Bia Lima", "Chefe Silva"}
    # Alerta: limite padrão de 3 pessoas do mesmo setor (Diretoria A: Ana e chefe; Bia é da A1) → baixa o limite para 2
    parametros = {k: v for k, v in cliente.get("/api/rh/parametros", headers=h["rh"]).json().items() if k not in ("atualizado_por_nome", "atualizado_em")}
    cliente.put("/api/rh/parametros", json={**parametros, "limite_alerta_setor": 2}, headers=h["rh"])
    alertas = cliente.get(f"{URL}/painel", params=params, headers=h["chefe"]).json()["alertas"]
    assert alertas == [{"setor": "Diretoria A", "inicio": "2026-11-10", "fim": "2026-11-12", "pessoas": 2}]
    # Anual e exportações
    assert len(cliente.get(f"{URL}/painel", params={"visao": "anual", "ano": 2026}, headers=h["rh"]).json()["periodos"]) == 3
    pdf = cliente.get(f"{URL}/painel/exportar", params={**params, "formato": "pdf"}, headers=h["rh"])
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    xlsx = cliente.get(f"{URL}/painel/exportar", params={**params, "formato": "xlsx"}, headers=h["rh"])
    assert xlsx.content[:2] == b"PK" and "ferias-licencas-2026-11.xlsx" in xlsx.headers["content-disposition"]
    with FabricaSessao() as sessao:
        assert sessao.query(Usuario).count() >= 5
