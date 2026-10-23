# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar que "quem é o RH" vem da ACL do recurso `rh` (e não do nome de um setor) e que os setores são geridos pelo RH.
"""Recurso ACL `rh`: Controle total = é o RH; Modificação = gere setores e cargos; Leitura = consulta. Sem regras, vale o setor `setor_cgp`."""

from tests.apoio_rh import criar_cgp
from tests.conftest import cabecalho, criar_usuario


def _regra(cliente, admin, recurso_id, nivel, usuarios_ids=(), setores_ids=()):
    r = cliente.post("/api/acl/regras", json={"recurso_id": recurso_id, "nivel": nivel, "usuarios_ids": list(usuarios_ids), "setores_ids": list(setores_ids)}, headers=admin)
    assert r.status_code == 201, r.text


def _recurso_rh(cliente, admin) -> int:
    r = cliente.post("/api/acl/recursos", json={"nome": "RH", "slug": "rh"}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_sem_regras_vale_o_setor_configurado_como_cgp(cliente, admin):
    membro = criar_usuario("membro-cgp", nome_completo="Membro CGP")
    outro = criar_usuario("outro-rh", nome_completo="Outro")
    criar_cgp(membro)
    assert cliente.get("/api/rh/papeis", headers=cabecalho(cliente, "membro-cgp")).json()["cgp"] is True
    assert cliente.get("/api/rh/papeis", headers=cabecalho(cliente, "outro-rh")).json()["cgp"] is False


def test_com_o_recurso_rh_configurado_a_acl_define_quem_e_o_rh(cliente, admin):
    """O setor CGP deixa de valer: só quem a ACL contempla é o RH, e o nível decide o que cada um faz com os setores."""
    do_setor_cgp = criar_usuario("no-setor-cgp", nome_completo="No Setor CGP")
    o_rh = criar_usuario("o-rh", nome_completo="O RH")
    gestor_setores = criar_usuario("gestor-setores", nome_completo="Gestor de Setores")
    leitor = criar_usuario("leitor-rh", nome_completo="Leitor")
    criar_cgp(do_setor_cgp)
    recurso = _recurso_rh(cliente, admin)
    _regra(cliente, admin, recurso, "CONTROLE_TOTAL", [o_rh])
    _regra(cliente, admin, recurso, "MODIFICACAO", [gestor_setores])
    _regra(cliente, admin, recurso, "LEITURA", [leitor])
    papeis = {login: cliente.get("/api/rh/papeis", headers=cabecalho(cliente, login)).json()["cgp"] for login in ("no-setor-cgp", "o-rh", "gestor-setores", "leitor-rh")}
    assert papeis == {"no-setor-cgp": False, "o-rh": True, "gestor-setores": False, "leitor-rh": False}

    # Setores: quem tem Gerir setores e cargos (e o RH) cria; leitura só consulta; quem não está na ACL do RH não cria
    corpo = {"nome": "Setor Novo do RH"}
    assert cliente.post("/api/setores", json=corpo, headers=cabecalho(cliente, "gestor-setores")).status_code == 201
    assert cliente.post("/api/setores", json={"nome": "Outro Setor"}, headers=cabecalho(cliente, "o-rh")).status_code == 201
    assert cliente.post("/api/setores", json={"nome": "Negado 1"}, headers=cabecalho(cliente, "leitor-rh")).status_code == 403
    assert cliente.post("/api/setores", json={"nome": "Negado 2"}, headers=cabecalho(cliente, "no-setor-cgp")).status_code == 403
    assert cliente.get("/api/setores", headers=cabecalho(cliente, "leitor-rh")).status_code == 200
    # Grupo sistêmico continua só do SuperRoot, mesmo para o RH
    assert cliente.post("/api/setores", json={"nome": "Grupo X", "sistemico": True}, headers=cabecalho(cliente, "o-rh")).status_code == 403
