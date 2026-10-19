# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar os perfis de acesso, a troca de perfil ativo e a personificação de usuários.
"""Testes dos perfis de acesso: soma com setor/regra direta, perfil ativo, administração (SuperRoot),
personificação (claims `imp`/`pa`) e auditoria com o autor real.
"""

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models import RegistroAuditoria
from tests.conftest import cabecalho, criar_usuario
from tests.test_acl import _nivel_efetivo, _recurso, _regra, _setor


def _perfil(cliente, admin, nome="Consulta", direitos=(), usuarios=()):
    r = cliente.post("/api/acl/perfis", json={"nome": nome}, headers=admin)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    # `direitos`: pares (recurso, ação) ou (recurso, [ações]); as ações são independentes
    por_recurso: dict[int, list[str]] = {}
    for recurso_id, acao in direitos:
        por_recurso.setdefault(recurso_id, []).extend([acao] if isinstance(acao, str) else acao)
    for recurso_id, acoes in por_recurso.items():
        r = cliente.put(f"/api/acl/perfis/{pid}/modulos/{recurso_id}", json={"acoes": acoes}, headers=admin)
        assert r.status_code == 200, r.text
    if usuarios:
        r = cliente.put(f"/api/acl/perfis/{pid}/usuarios", json={"usuarios_ids": list(usuarios)}, headers=admin)
        assert r.status_code == 200, r.text
    return pid


def test_perfil_libera_e_fecha_o_modulo(cliente, admin):
    ana, bia = criar_usuario("ana"), criar_usuario("bia")
    rid = _recurso(cliente, admin)
    _perfil(cliente, admin, direitos=[(rid, "LEITURA")], usuarios=[ana])
    assert _nivel_efetivo(cliente, admin, ana) == "LEITURA"
    assert _nivel_efetivo(cliente, admin, bia) is None
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "bia")).status_code == 403
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "ana")).status_code == 200


def test_soma_perfil_setor_e_direta(cliente, admin):
    ana = criar_usuario("ana")
    rid = _recurso(cliente, admin)
    _perfil(cliente, admin, direitos=[(rid, "LEITURA")], usuarios=[ana])
    _regra(cliente, admin, rid, "MODIFICACAO", setores=[_setor(cliente, admin, "S", [ana])])
    assert _nivel_efetivo(cliente, admin, ana) == "MODIFICACAO"
    efetivo = {a["slug"]: a for a in cliente.get(f"/api/acl/efetivo/{ana}", headers=admin).json()}["usuarios"]
    assert efetivo["origens"] == {"perfil": "LEITURA", "setor": "MODIFICACAO"}


def test_so_o_perfil_ativo_vale_e_troca_de_perfil(cliente, admin):
    ana = criar_usuario("ana")
    rid = _recurso(cliente, admin)
    p1 = _perfil(cliente, admin, "A leitura", [(rid, "LEITURA")], [ana])
    p2 = _perfil(cliente, admin, "B total", [(rid, "CONTROLE_TOTAL")], [ana])
    # O padrão é o primeiro por nome
    h = cabecalho(cliente, "ana")
    sessao = cliente.get("/api/autenticacao/sessao", headers=h).json()
    assert [p["nome"] for p in sessao["perfis"]] == ["A leitura", "B total"]
    assert sessao["perfil_ativo"]["id"] == p1
    r = cliente.post("/api/autenticacao/perfil-ativo", json={"perfil_id": p2}, headers=h)
    assert r.status_code == 200, r.text
    h2 = {"Authorization": f"Bearer {r.json()['token_acesso']}"}
    assert cliente.get("/api/autenticacao/sessao", headers=h2).json()["perfil_ativo"]["id"] == p2
    niveis = {a["slug"]: a["nivel"] for a in cliente.get("/api/acl/meus-acessos", headers=h2).json()}
    assert niveis["usuarios"] == "CONTROLE_TOTAL"


def test_perfil_ativo_de_outro_usuario_e_recusado(cliente, admin):
    ana, _ = criar_usuario("ana"), criar_usuario("bia")
    rid = _recurso(cliente, admin)
    outro = _perfil(cliente, admin, "Outro", [(rid, "LEITURA")], [])
    _perfil(cliente, admin, "Meu", [(rid, "LEITURA")], [ana])
    r = cliente.post("/api/autenticacao/perfil-ativo", json={"perfil_id": outro}, headers=cabecalho(cliente, "ana"))
    assert r.status_code == 403


def test_administracao_de_perfis_so_superroot(cliente, admin):
    criar_usuario("ana")
    h = cabecalho(cliente, "ana")
    assert cliente.get("/api/acl/perfis", headers=h).status_code == 403
    assert cliente.post("/api/acl/perfis", json={"nome": "X"}, headers=h).status_code == 403
    assert cliente.post("/api/autenticacao/personificar", json={"usuario_id": 1}, headers=h).status_code == 403


def test_nome_unico_e_exclusao_de_perfil_em_uso(cliente, admin):
    ana = criar_usuario("ana")
    pid = _perfil(cliente, admin, "Gestão", usuarios=[ana])
    assert cliente.post("/api/acl/perfis", json={"nome": "gestão"}, headers=admin).status_code == 409
    assert cliente.delete(f"/api/acl/perfis/{pid}", headers=admin).status_code == 409
    cliente.put(f"/api/acl/perfis/{pid}/usuarios", json={"usuarios_ids": []}, headers=admin)
    assert cliente.delete(f"/api/acl/perfis/{pid}", headers=admin).status_code == 204
    assert cliente.get(f"/api/acl/perfis/{pid}", headers=admin).status_code == 404


def test_perfis_do_usuario_com_um_so_padrao(cliente, admin):
    ana = criar_usuario("ana")
    p1, p2 = _perfil(cliente, admin, "A"), _perfil(cliente, admin, "B")
    r = cliente.put(f"/api/acl/usuarios/{ana}/perfis", json={"perfis_ids": [p1, p2], "padrao_id": p2}, headers=admin)
    assert r.status_code == 200, r.text
    assert {p["perfil_id"]: p["padrao"] for p in r.json()} == {p1: False, p2: True}
    r = cliente.put(f"/api/acl/usuarios/{ana}/perfis", json={"perfis_ids": [p1], "padrao_id": p2}, headers=admin)
    assert r.status_code == 400


def test_perfil_inativo_nao_vale(cliente, admin):
    ana = criar_usuario("ana")
    rid = _recurso(cliente, admin)
    pid = _perfil(cliente, admin, "P", [(rid, "LEITURA")], [ana])
    cliente.put(f"/api/acl/perfis/{pid}", json={"nome": "P", "ativo": False}, headers=admin)
    # Sem perfis ativos nem regras, o módulo volta a ficar aberto
    assert _nivel_efetivo(cliente, admin, ana) == "CONTROLE_TOTAL"


def test_personificar_trocar_parar_e_auditar(cliente, admin):
    ana = criar_usuario("ana")
    rid = _recurso(cliente, admin)
    _perfil(cliente, admin, "P", [(rid, "LEITURA")], [ana])
    r = cliente.post("/api/autenticacao/personificar", json={"usuario_id": ana}, headers=admin)
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['token_acesso']}"}
    sessao = cliente.get("/api/autenticacao/sessao", headers=h).json()
    assert sessao["login"] == "ana" and sessao["personificado_por"]["login"] == "root"
    # Enquanto personifica, vale o acesso de ana (somente leitura) e não o do SuperRoot
    assert {a["slug"]: a["nivel"] for a in cliente.get("/api/acl/meus-acessos", headers=h).json()}["usuarios"] == "LEITURA"
    assert cliente.get("/api/acl/perfis", headers=h).status_code == 403
    # Trocar de alvo durante a personificação é permitido (o autor real continua sendo o SuperRoot)
    assert cliente.post("/api/autenticacao/personificar", json={"usuario_id": ana}, headers=h).status_code == 200
    # Ação feita personificando é auditada com o autor real
    cliente.post("/api/autenticacao/perfil-ativo", json={"perfil_id": 1}, headers=h)
    with FabricaSessao() as s:
        registros = list(s.scalars(select(RegistroAuditoria).where(RegistroAuditoria.personificado_por_id.is_not(None))))
    assert all("(por root)" in x.autor for x in registros)
    # Parar devolve a sessão do SuperRoot
    r = cliente.post("/api/autenticacao/personificar/parar", headers=h)
    assert r.status_code == 200, r.text
    h0 = {"Authorization": f"Bearer {r.json()['token_acesso']}"}
    sessao = cliente.get("/api/autenticacao/sessao", headers=h0).json()
    assert sessao["login"] == "root" and sessao["personificado_por"] is None
    assert cliente.post("/api/autenticacao/personificar/parar", headers=h0).status_code == 422


def test_personificar_inativo_ou_a_si_mesmo(cliente, admin):
    ana = criar_usuario("ana", ativo=False) if "ativo" in criar_usuario.__code__.co_varnames else None
    root_id = cliente.get("/api/autenticacao/sessao", headers=admin).json()["id"]
    assert cliente.post("/api/autenticacao/personificar", json={"usuario_id": root_id}, headers=admin).status_code == 422
    if ana:
        assert cliente.post("/api/autenticacao/personificar", json={"usuario_id": ana}, headers=admin).status_code == 422


def test_acoes_do_perfil_sao_independentes(cliente, admin):
    """Só a ação marcada abre a porta: Modificação sem Leitura grava, mas não consulta."""
    ana = criar_usuario("ana")
    rid = cliente.post("/api/acl/recursos", json={"nome": "SLA de prazos", "slug": "sla"}, headers=admin).json()["id"]
    acoes = {a["codigo"] for a in cliente.get("/api/acl/recursos", headers=admin).json()[0]["acoes"]}
    assert {"LEITURA", "MODIFICACAO"} <= acoes
    _perfil(cliente, admin, "Só grava", [(rid, ["MODIFICACAO"])], [ana])
    h = cabecalho(cliente, "ana")
    assert cliente.get("/api/sla/politicas", headers=h).status_code == 403
    politicas = cliente.get("/api/sla/politicas", headers=admin).json()
    assert cliente.put("/api/sla/politicas", json={"politicas": politicas[:1]}, headers=h).status_code == 200


def test_modulo_no_perfil_valida_acoes_e_pode_ser_removido(cliente, admin):
    rid = _recurso(cliente, admin)
    pid = _perfil(cliente, admin, "P")
    assert cliente.get(f"/api/acl/perfis/{pid}", headers=admin).json()["direitos"] == []  # nasce em branco
    assert cliente.put(f"/api/acl/perfis/{pid}/modulos/{rid}", json={"acoes": []}, headers=admin).status_code == 422
    assert cliente.put(f"/api/acl/perfis/{pid}/modulos/9999", json={"acoes": ["LEITURA"]}, headers=admin).status_code == 400
    r = cliente.put(f"/api/acl/perfis/{pid}/modulos/{rid}", json={"acoes": ["CONTROLE_TOTAL", "LEITURA"]}, headers=admin)
    assert r.status_code == 200
    assert r.json()["direitos"][0]["acoes"] == ["LEITURA", "CONTROLE_TOTAL"]
    r = cliente.delete(f"/api/acl/perfis/{pid}/modulos/{rid}", headers=admin)
    assert r.status_code == 200 and r.json()["direitos"] == []
    assert cliente.delete(f"/api/acl/perfis/{pid}/modulos/{rid}", headers=admin).status_code == 404


def test_perfil_por_setor_membros_recebem_o_perfil_e_o_acesso(cliente, admin):
    """Setor ou grupo sistêmico recebe o perfil: os membros passam a ter o perfil (e o acesso), sem atribuição direta; quem sai do setor perde."""
    ana, bia = criar_usuario("ana"), criar_usuario("bia")
    rid = _recurso(cliente, admin)
    pid = _perfil(cliente, admin, "Consulta por setor", direitos=[(rid, "LEITURA")])
    sid = _setor(cliente, admin, "Financeiro", [ana])
    # Sem o setor no perfil, a Ana não acessa (o módulo está fechado pelo perfil)
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "ana")).status_code == 403
    assert cliente.put(f"/api/acl/perfis/{pid}/setores", json={"setores_ids": [99999]}, headers=admin).status_code == 400
    r = cliente.put(f"/api/acl/perfis/{pid}/setores", json={"setores_ids": [sid]}, headers=admin)
    assert r.status_code == 200 and [s["nome"] for s in r.json()["setores"]] == ["Financeiro"] and r.json()["total_setores"] == 1
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "ana")).status_code == 200
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "bia")).status_code == 403
    # A ficha mostra de onde vem; o perfil por setor não é alterável pela ficha do usuário e entra no menu (perfis da sessão)
    perfis = cliente.get(f"/api/acl/usuarios/{ana}/perfis", headers=admin).json()
    assert perfis == [{"perfil_id": pid, "nome": "Consulta por setor", "ativo": True, "padrao": False, "via_setores": ["Financeiro"], "direto": False}]
    sessao = cliente.get("/api/autenticacao/sessao", headers=cabecalho(cliente, "ana")).json()
    assert [p["id"] for p in sessao["perfis"]] == [pid] and sessao["perfil_ativo"]["id"] == pid
    assert cliente.put(f"/api/acl/usuarios/{ana}/perfis", json={"perfis_ids": [], "padrao_id": None}, headers=admin).status_code == 200
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "ana")).status_code == 200  # continua pelo setor
    # Quem sai do setor perde o perfil; tirar o setor do perfil também
    cliente.put(f"/api/setores/{sid}", json={"nome": "Financeiro", "membros_ids": [bia]}, headers=admin)
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "ana")).status_code == 403
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "bia")).status_code == 200
    cliente.put(f"/api/acl/perfis/{pid}/setores", json={"setores_ids": []}, headers=admin)
    assert cliente.get("/api/usuarios", headers=cabecalho(cliente, "bia")).status_code == 403
