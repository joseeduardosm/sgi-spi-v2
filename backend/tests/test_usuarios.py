# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o cadastro e a consulta de usuários.

from datetime import timedelta

from sqlalchemy import select

from app.core.banco import FabricaSessao, agora_utc
from app.models import RegistroAuditoria, Usuario
from tests.conftest import PERFIL_COMPLETO, cabecalho, criar_usuario


def _nova_conta(cliente, admin, login="ana", **extra):
    corpo = {"login": login, "senha": "senha-forte-1", "perfil": {"nome_completo": "Ana"}, **extra}
    return cliente.post("/api/usuarios", json=corpo, headers=admin)


# --- Cadastro pelo SuperRoot -------------------------------------------------

def test_superroot_cria_conta_local(cliente, admin):
    r = _nova_conta(cliente, admin)
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["origem"] == "local" and corpo["possui_senha_local"] is True and corpo["superusuario"] is False
    assert cliente.post("/api/autenticacao/login", json={"login": "ana", "senha": "senha-forte-1"}).status_code == 200


def test_login_duplicado_409_e_senha_curta_422(cliente, admin):
    _nova_conta(cliente, admin)
    r = _nova_conta(cliente, admin, login="ANA")
    assert r.status_code == 409 and r.json()["codigo"] == "conflito"
    r = cliente.post("/api/usuarios", json={"login": "bia", "senha": "curta"}, headers=admin)
    assert r.status_code == 422 and r.json()["erros"][0] == {"campo": "senha", "mensagem": "deve ter ao menos 8 caractere(s)"}


def test_edicao_de_dados_privilegios_e_senha(cliente, admin):
    uid = _nova_conta(cliente, admin).json()["id"]
    dados = {"ativo": True, "superusuario": True, "senha": "outra-senha-1", "perfil": PERFIL_COMPLETO}
    r = cliente.put(f"/api/usuarios/{uid}", json=dados, headers=admin)
    assert r.status_code == 200 and r.json()["superusuario"] is True
    assert r.json()["perfil"]["cargo"] == "Analista"
    assert cliente.post("/api/autenticacao/login", json={"login": "ana", "senha": "outra-senha-1"}).status_code == 200


def test_conta_principal_protegida(cliente, admin):
    root_id = cliente.get("/api/autenticacao/sessao", headers=admin).json()["id"]
    r = cliente.delete(f"/api/usuarios/{root_id}", headers=admin)
    assert r.status_code == 400 and "principal" in r.json()["detalhe"] and r.json()["codigo"] == "invalido"
    r = cliente.put(f"/api/usuarios/{root_id}", json={"ativo": False, "superusuario": True, "perfil": {}}, headers=admin)
    assert r.status_code == 400


def test_exclusao_e_auditoria(cliente, admin):
    uid = _nova_conta(cliente, admin).json()["id"]
    assert cliente.delete(f"/api/usuarios/{uid}", headers=admin).status_code == 204
    assert cliente.get(f"/api/usuarios/{uid}", headers=admin).status_code == 404
    with FabricaSessao() as sessao:
        acoes = list(sessao.scalars(select(RegistroAuditoria.acao).order_by(RegistroAuditoria.id)))
    assert acoes == ["usuario.criar", "usuario.excluir"]


def test_gestor_invalido_ou_proprio(cliente, admin):
    uid = _nova_conta(cliente, admin).json()["id"]
    r = cliente.put(f"/api/usuarios/{uid}", json={"ativo": True, "superusuario": False, "perfil": {"gestor_id": uid}}, headers=admin)
    assert r.status_code == 400
    r = cliente.put(f"/api/usuarios/{uid}", json={"ativo": True, "superusuario": False, "perfil": {"gestor_id": 9999}}, headers=admin)
    assert r.status_code == 400


def test_listagem_pesquisa_e_paginacao(cliente, admin):
    for i in range(3):
        criar_usuario(f"usuario{i}", nome_completo=f"Fulano {i}", departamento="Financeiro" if i == 0 else "Contratos")
    r = cliente.get("/api/usuarios", params={"busca": "financeiro"}, headers=admin).json()
    assert r["total"] == 1 and r["itens"][0]["login"] == "usuario0"
    r = cliente.get("/api/usuarios", params={"tamanho_pagina": 2}, headers=admin).json()
    assert r["total"] == 4 and len(r["itens"]) == 2 and r["pagina"] == 1


def test_usuario_comum_nao_administra(cliente, admin):
    criar_usuario("comum")
    h = cabecalho(cliente, "comum")
    assert cliente.get("/api/usuarios", headers=h).status_code == 200  # recurso aberto: leitura permitida
    r = _nova_conta(cliente, h)
    assert r.status_code == 403 and r.json()["codigo"] == "acesso_negado"


# --- Perfil institucional e revalidação --------------------------------------

def test_perfil_incompleto_restringe_acesso(cliente):
    criar_usuario("novo", completo=False)
    h = cabecalho(cliente, "novo")
    sessao_atual = cliente.get("/api/autenticacao/sessao", headers=h).json()
    assert sessao_atual["perfil_restrito"] is True and "ramal" in sessao_atual["campos_pendentes"]
    r = cliente.get("/api/usuarios", headers=h)
    assert r.status_code == 403 and r.json()["codigo"] == "revisao_perfil_obrigatoria"
    assert cliente.get("/api/autenticacao/perfil", headers=h).status_code == 200
    assert cliente.get("/api/autenticacao/perfil/opcoes-gestor", headers=h).status_code == 200


def test_revalidacao_libera_acesso(cliente):
    criar_usuario("novo", completo=False)
    h = cabecalho(cliente, "novo")
    r = cliente.put("/api/autenticacao/perfil", json={**PERFIL_COMPLETO, "ramal": ""}, headers=h)
    assert r.status_code == 422 and "ramal" in r.json()["detalhe"]
    r = cliente.put("/api/autenticacao/perfil", json=PERFIL_COMPLETO, headers=h)
    assert r.status_code == 200 and r.json()["perfil_restrito"] is False
    assert cliente.get("/api/usuarios", headers=h).status_code == 200


def test_revalidacao_vencida_apos_30_dias(cliente):
    uid = criar_usuario("antigo")
    with FabricaSessao() as sessao:
        sessao.get(Usuario, uid).perfil_revisado_em = agora_utc() - timedelta(days=31)
        sessao.commit()
    h = cabecalho(cliente, "antigo")
    assert cliente.get("/api/autenticacao/sessao", headers=h).json()["revisao_obrigatoria"] is True
    assert cliente.get("/api/usuarios", headers=h).json()["codigo"] == "revisao_perfil_obrigatoria"


def test_superroot_nao_passa_pela_restricao(cliente, admin):
    assert cliente.get("/api/autenticacao/sessao", headers=admin).json()["perfil_restrito"] is False
    assert cliente.get("/api/usuarios", headers=admin).status_code == 200


def test_ldap_nao_possui_senha_local_ate_admin_definir(cliente, admin):
    with FabricaSessao() as sessao:
        usuario = Usuario(login="corp", origem="ldap", nome_completo="Corp")
        sessao.add(usuario)
        sessao.commit()
        uid = usuario.id
    assert cliente.get(f"/api/usuarios/{uid}", headers=admin).json()["possui_senha_local"] is False
    r = cliente.put(f"/api/usuarios/{uid}", json={"ativo": True, "superusuario": False, "senha": "contingencia-1", "perfil": {}}, headers=admin)
    assert r.json()["origem"] == "local_ldap" and r.json()["possui_senha_local"] is True
