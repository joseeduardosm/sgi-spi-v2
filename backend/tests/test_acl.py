# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar as regras do controle de acesso (ACL).

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models import RecursoAcl, RegistroAuditoria
from tests.conftest import cabecalho, criar_usuario


def _recurso(cliente, admin, slug="usuarios", nome="Usuários"):
    r = cliente.post("/api/acl/recursos", json={"nome": nome, "slug": slug}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _regra(cliente, admin, recurso_id, nivel, usuarios=(), setores=()):
    corpo = {"recurso_id": recurso_id, "nivel": nivel, "usuarios_ids": list(usuarios), "setores_ids": list(setores)}
    r = cliente.post("/api/acl/regras", json=corpo, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _setor(cliente, admin, nome, membros):
    r = cliente.post("/api/setores", json={"nome": nome, "membros_ids": membros}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _nivel_efetivo(cliente, admin, usuario_id, slug="usuarios"):
    return {a["slug"]: a["nivel"] for a in cliente.get(f"/api/acl/efetivo/{usuario_id}", headers=admin).json()}[slug]


def test_recurso_sem_regras_e_aberto(cliente, admin):
    criar_usuario("maria")
    _recurso(cliente, admin)
    h = cabecalho(cliente, "maria")
    assert cliente.get("/api/usuarios", headers=h).status_code == 200
    niveis = {a["slug"]: a["nivel"] for a in cliente.get("/api/acl/meus-acessos", headers=h).json()}
    assert niveis["usuarios"] == "CONTROLE_TOTAL"


def test_primeira_regra_vira_lista_positiva(cliente, admin):
    maria = criar_usuario("maria")
    criar_usuario("joao")
    rid = _recurso(cliente, admin)
    _regra(cliente, admin, rid, "LEITURA", usuarios=[maria])
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "maria")).status_code == 200
    r = cliente.get("/api/usuarios", headers=cabecalho(cliente, "joao"))
    assert r.status_code == 403
    corpo = r.json()
    assert corpo["codigo"] == "acl_negado" and corpo["recurso"] == "usuarios"
    assert corpo["nivel_exigido"] == "LEITURA" and corpo["nivel_efetivo"] is None
    assert "usuarios" not in {a["slug"] for a in cliente.get("/api/acl/meus-acessos", headers=cabecalho(cliente, "joao")).json()}


def test_heranca_por_setor_e_prioridade_da_regra_direta(cliente, admin):
    ana, bia = criar_usuario("ana"), criar_usuario("bia")
    rid = _recurso(cliente, admin)
    sid = _setor(cliente, admin, "Contratos", [ana, bia])
    _regra(cliente, admin, rid, "CONTROLE_TOTAL", setores=[sid])
    _regra(cliente, admin, rid, "LEITURA", usuarios=[bia])  # direta prevalece, mesmo sendo menor
    assert _nivel_efetivo(cliente, admin, ana) == "CONTROLE_TOTAL"
    assert _nivel_efetivo(cliente, admin, bia) == "LEITURA"


def test_maior_nivel_entre_regras_diretas(cliente, admin):
    ana = criar_usuario("ana")
    rid = _recurso(cliente, admin)
    _regra(cliente, admin, rid, "LEITURA", usuarios=[ana])
    _regra(cliente, admin, rid, "MODIFICACAO", usuarios=[ana])
    assert _nivel_efetivo(cliente, admin, ana) == "MODIFICACAO"


def test_recurso_inativo_volta_a_ser_aberto(cliente, admin):
    criar_usuario("joao")
    outra = criar_usuario("outra")
    rid = _recurso(cliente, admin)
    _regra(cliente, admin, rid, "LEITURA", usuarios=[outra])
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "joao")).status_code == 403
    cliente.put(f"/api/acl/recursos/{rid}", json={"nome": "Usuários", "slug": "usuarios", "ativo": False}, headers=admin)
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "joao")).status_code == 200


def test_superroot_sempre_controle_total(cliente, admin):
    outra = criar_usuario("outra")
    rid = _recurso(cliente, admin)
    _regra(cliente, admin, rid, "LEITURA", usuarios=[outra])
    assert cliente.get("/api/usuarios", headers=admin).status_code == 200
    assert all(a["nivel"] == "CONTROLE_TOTAL" for a in cliente.get("/api/acl/meus-acessos", headers=admin).json())


def test_validacoes_de_recurso_e_regra(cliente, admin):
    rid = _recurso(cliente, admin, slug="  Meu Módulo! ", nome="Meu módulo")
    with FabricaSessao() as sessao:
        assert sessao.get(RecursoAcl, rid).slug == "meu-m-dulo"
    assert cliente.post("/api/acl/recursos", json={"nome": "meu MÓDULO", "slug": "x"}, headers=admin).status_code == 409
    r = cliente.post("/api/acl/regras", json={"recurso_id": rid, "nivel": "LEITURA", "usuarios_ids": [], "setores_ids": []}, headers=admin)
    assert r.status_code == 400
    r = cliente.post("/api/acl/regras", json={"recurso_id": rid, "nivel": "TUDO", "usuarios_ids": [1]}, headers=admin)
    assert r.status_code == 422 and r.json()["erros"][0]["campo"] == "nivel"


def test_administracao_restrita_e_auditada(cliente, admin):
    criar_usuario("maria")
    h = cabecalho(cliente, "maria")
    assert cliente.get("/api/acl/recursos", headers=h).status_code == 403
    assert cliente.post("/api/acl/regras", json={"recurso_id": 1, "nivel": "LEITURA", "usuarios_ids": [1]}, headers=h).status_code == 403
    rid = _recurso(cliente, admin)
    regra = _regra(cliente, admin, rid, "LEITURA", usuarios=[1])
    assert cliente.delete(f"/api/acl/regras/{regra}", headers=admin).status_code == 204
    with FabricaSessao() as sessao:
        acoes = list(sessao.scalars(select(RegistroAuditoria.acao).order_by(RegistroAuditoria.id)))
    assert acoes == ["acl.recurso.criar", "acl.regra.criar", "acl.regra.excluir"]


def test_setores_regras_de_integridade(cliente, admin):
    ana = criar_usuario("ana")
    pai = _setor(cliente, admin, "Secretaria", [])
    filho = cliente.post("/api/setores", json={"nome": "Diretoria", "setor_pai_id": pai, "membros_ids": [ana]}, headers=admin).json()["id"]
    assert cliente.post("/api/setores", json={"nome": "secretaria"}, headers=admin).status_code == 409
    assert cliente.put(f"/api/setores/{pai}", json={"nome": "Secretaria", "setor_pai_id": filho}, headers=admin).status_code == 400  # ciclo
    assert cliente.delete(f"/api/setores/{pai}", headers=admin).status_code == 400  # tem subordinado
    assert cliente.delete(f"/api/setores/{filho}", headers=admin).status_code == 400  # tem membros
    detalhe = cliente.get(f"/api/setores/{filho}", headers=admin).json()
    assert detalhe["setor_pai_nome"] == "Secretaria" and [m["id"] for m in detalhe["membros"]] == [ana]
    assert cliente.get(f"/api/usuarios/{ana}", headers=admin).json()["setores"] == ["Diretoria"]
