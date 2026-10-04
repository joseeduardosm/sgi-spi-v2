# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o Painel Executivo: acesso por ACL, slides de contratos, RH e tarefas, cache e PDF.
"""Painel Executivo (`/api/painel-executivo`)."""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO

import pytest
from pypdf import PdfReader

from app.core.banco import FabricaSessao
from app.models.rh import Afastamento
from app.services.painel_executivo import cache
from tests.apoio_contratos import criar_contrato
from tests.apoio_rh import simular_smtp
from tests.conftest import cabecalho, criar_usuario

URL = "/api/painel-executivo"


@pytest.fixture(autouse=True)
def _limpar(monkeypatch):
    simular_smtp(monkeypatch)
    cache.limpar()
    yield
    cache.limpar()


@pytest.fixture
def pessoas(cliente, admin):
    """Dora (Diretoria) recebe LEITURA no recurso; Eli não recebe nada."""
    ids = {login: criar_usuario(login, nome_completo=nome, email=f"{login}@sp.gov.br", departamento="Contratos")
           for login, nome in (("dora", "Dora Diretora"), ("eli", "Eli Comum"))}
    return ids, {k: cabecalho(cliente, k) for k in ids}


def _conceder(cliente, admin, usuario_id: int) -> None:
    recursos = cliente.get("/api/acl/recursos", headers=admin).json()
    recurso = next((r for r in recursos if r["slug"] == "painel-executivo"), None)
    if recurso is None:
        recurso = cliente.post("/api/acl/recursos", json={"nome": "Painel Executivo", "slug": "painel-executivo"}, headers=admin).json()
    r = cliente.post("/api/acl/regras", json={"recurso_id": recurso["id"], "nivel": "LEITURA", "usuarios_ids": [usuario_id], "setores_ids": []}, headers=admin)
    assert r.status_code == 201, r.text


def test_sem_regras_so_o_superroot_acessa(cliente, admin, pessoas):
    ids, h = pessoas
    assert cliente.get(f"{URL}/contratos").status_code == 401
    # Recurso ainda sem regras: ninguém além do SuperRoot
    assert cliente.get(f"{URL}/acesso", headers=h["dora"]).json() == {"pode": False}
    assert cliente.get(f"{URL}/tarefas", headers=h["dora"]).status_code == 403
    assert cliente.get(f"{URL}/acesso", headers=admin).json() == {"pode": True}
    assert cliente.get(f"{URL}/tarefas", headers=admin).status_code == 200


def test_regra_libera_so_quem_foi_citado(cliente, admin, pessoas):
    ids, h = pessoas
    _conceder(cliente, admin, ids["dora"])
    assert cliente.get(f"{URL}/acesso", headers=h["dora"]).json() == {"pode": True}
    assert cliente.get(f"{URL}/rh", headers=h["dora"]).status_code == 200
    assert cliente.get(f"{URL}/acesso", headers=h["eli"]).json() == {"pode": False}
    for caminho in ("contratos", "rh", "tarefas", "contratos/pdf"):
        r = cliente.get(f"{URL}/{caminho}", headers=h["eli"])
        assert r.status_code == 403, caminho
    r = cliente.get(f"{URL}/tarefas", headers=h["eli"])
    assert r.status_code == 403 and r.json()["codigo"] == "acl_negado"


def test_slide_de_contratos_traz_execucao_acumulada_e_vencimentos(cliente, admin):
    hoje = date.today()
    criar_contrato(cliente, admin, numero="001/2026", data_inicio=date(hoje.year, 1, 1).isoformat())
    r = cliente.get(f"{URL}/contratos", headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["exercicio"] == hoje.year and d["numeros"]["contratos_ativos"] == 1
    assert len(d["execucao"]["meses"]) == 12 and len(d["acumulado"]) == 12
    # O acumulado nunca diminui e termina no total do exercício
    previstos = [float(p["previsto"]) for p in d["acumulado"]]
    assert previstos == sorted(previstos) and f"{previstos[-1]:.2f}" == d["execucao"]["total_previsto"]
    assert [v["ate_dias"] for v in d["vencimentos"]] == [30, 60, 90]
    assert cliente.get(f"{URL}/contratos", params={"exercicio": 1999}, headers=admin).status_code == 422


def test_slide_de_rh_mostra_quem_esta_fora_hoje(cliente, admin, pessoas):
    ids, h = pessoas
    hoje = date.today()
    with FabricaSessao() as s:
        s.add(Afastamento(usuario_id=ids["eli"], tipo="ferias", inicio=hoje - timedelta(days=2), fim=hoje + timedelta(days=5), dias=8,
                          exercicio=hoje.year, status="aprovado"))
        s.add(Afastamento(usuario_id=ids["dora"], tipo="ferias", inicio=hoje + timedelta(days=30), fim=hoje + timedelta(days=40), dias=11,
                          exercicio=hoje.year, status="pendente"))
        s.commit()
    d = cliente.get(f"{URL}/rh", headers=admin).json()
    assert [(a["nome"], a["tipo"]) for a in d["afastados_hoje"]] == [("Eli Comum", "ferias")]
    assert len(d["por_mes"]) == 12 and sum(m["ferias"] for m in d["por_mes"]) >= 1
    assert d["por_setor"][0]["setor"] == "Contratos" and d["por_setor"][0]["pessoas"] == 1


def test_slide_de_tarefas_agrega_a_organizacao(cliente, admin, pessoas):
    ids, h = pessoas
    r = cliente.post("/api/tarefas/equipes", json={"nome": "Diretoria", "lideres_ids": [ids["dora"]], "membros_ids": [ids["eli"]]}, headers=h["dora"])
    assert r.status_code == 201, r.text
    equipe_id = r.json()["id"]

    def prazo(dias):
        return (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat()
    for titulo, dias in (("Em dia", 10), ("Vencida", -3)):
        r = cliente.post("/api/tarefas", json={"titulo": titulo, "descricao": "x", "prazo": prazo(dias), "equipe_id": equipe_id,
                                              "responsavel_id": ids["eli"]}, headers=h["dora"])
        assert r.status_code == 201, r.text
    d = cliente.get(f"{URL}/tarefas", headers=admin).json()
    assert d["abertas"] == 2 and d["atrasadas"] == 1
    assert len(d["semanas"]) == 12 and sum(s["criadas"] for s in d["semanas"]) == 2
    assert all(date.fromisoformat(s["inicio"]).weekday() == 0 for s in d["semanas"])


def test_cache_evita_recalcular_dentro_da_validade(cliente, admin, monkeypatch):
    from app.services.painel_executivo import slides
    chamadas = []
    original = slides.tarefas
    monkeypatch.setattr(slides, "tarefas", lambda sessao: (chamadas.append(1), original(sessao))[1])
    cliente.get(f"{URL}/tarefas", headers=admin)
    cliente.get(f"{URL}/tarefas", headers=admin)
    assert len(chamadas) == 1


@pytest.mark.parametrize("slide", ["contratos", "rh", "tarefas"])
def test_pdf_de_cada_slide_abre(cliente, admin, slide):
    r = cliente.get(f"{URL}/{slide}/pdf", headers=admin)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    texto = PdfReader(BytesIO(r.content)).pages[0].extract_text()
    assert "Painel Executivo" in texto
    assert cliente.get(f"{URL}/inexistente/pdf", headers=admin).status_code == 422
