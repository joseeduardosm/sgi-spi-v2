# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar os atalhos fixos da barra lateral (leitura para todos, cadastro por ACL e validação dos destinos).
"""Atalhos fixos: categorias e atalhos internos e externos; todos leem os ativos, só quem tem MODIFICACAO em `atalhos` gerencia."""

import pytest

from tests.conftest import cabecalho, criar_usuario

URL = "/api/atalhos"


@pytest.fixture(autouse=True)
def _gestao_fechada(cliente, admin):
    """Como a migração faz em produção: o recurso `atalhos` nasce com uma regra só para um gestor (sem regras, ficaria aberto a todos)."""
    gestor = criar_usuario("gestor_atalhos")
    recurso = cliente.post("/api/acl/recursos", json={"nome": "Atalhos", "slug": "atalhos"}, headers=admin).json()
    r = cliente.post("/api/acl/regras", json={"recurso_id": recurso["id"], "nivel": "MODIFICACAO", "usuarios_ids": [gestor], "setores_ids": []}, headers=admin)
    assert r.status_code == 201, r.text
    return gestor


def _categoria(cliente, h, nome="Sistemas", ordem=0, **extras):
    r = cliente.post(f"{URL}/categorias", json={"nome": nome, "ordem": ordem, **extras}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _atalho(cliente, h, categoria_id, titulo="Outlook", url="https://outlook.office.com/mail/", **extras):
    r = cliente.post(f"{URL}/itens", json={"categoria_id": categoria_id, "titulo": titulo, "url": url, **extras}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def test_todos_leem_os_ativos_ordenados_e_so_quem_gerencia_ve_o_resto(cliente, admin):
    criar_usuario("comum")
    comum = cabecalho(cliente, "comum")
    b = _categoria(cliente, admin, "Serviços", ordem=2)
    a = _categoria(cliente, admin, "Sistemas", ordem=1)
    vazia = _categoria(cliente, admin, "Sem atalhos", ordem=3)
    inativa = _categoria(cliente, admin, "Inativa", ordem=4, ativo=False)
    _atalho(cliente, admin, a["id"], "Contratos", "/contratos")
    externo = _atalho(cliente, admin, a["id"], "Outlook")
    _atalho(cliente, admin, a["id"], "Escondido", "/tarefas", ativo=False)
    _atalho(cliente, admin, b["id"], "D.O.E", "https://www.doe.sp.gov.br/", ordem=1)
    _atalho(cliente, admin, inativa["id"], "Em categoria inativa", "/ramais")
    # Interno abre na mesma aba; externo, em nova aba (padrão)
    assert externo["externo"] is True and externo["nova_aba"] is True
    lista = cliente.get(URL, headers=comum).json()["categorias"]
    assert [c["nome"] for c in lista] == ["Sistemas", "Serviços"]                      # ordem; sem vazia e sem inativa
    assert [(x["titulo"], x["externo"], x["nova_aba"]) for x in lista[0]["atalhos"]] == [("Contratos", False, False), ("Outlook", True, True)]
    # Gestão (inclui inativos e vazias) só para quem tem MODIFICACAO
    assert cliente.get(f"{URL}/gestao", headers=comum).status_code == 403
    todas = cliente.get(f"{URL}/gestao", headers=admin).json()["categorias"]
    assert [c["nome"] for c in todas] == ["Sistemas", "Serviços", "Sem atalhos", "Inativa"] and vazia["id"] in [c["id"] for c in todas]
    assert any(x["titulo"] == "Escondido" for c in todas for x in c["atalhos"])
    assert cliente.get(URL).status_code == 401


def test_so_quem_gerencia_cria_altera_e_exclui(cliente, admin):
    criar_usuario("comum")
    comum = cabecalho(cliente, "comum")
    assert cliente.post(f"{URL}/categorias", json={"nome": "X"}, headers=comum).status_code == 403
    categoria = _categoria(cliente, admin)
    atalho = _atalho(cliente, admin, categoria["id"])
    assert cliente.post(f"{URL}/itens", json={"categoria_id": categoria["id"], "titulo": "Y", "url": "/x"}, headers=comum).status_code == 403
    assert cliente.put(f"{URL}/itens/{atalho['id']}", json={"categoria_id": categoria["id"], "titulo": "Y", "url": "/x"}, headers=comum).status_code == 403
    assert cliente.delete(f"{URL}/itens/{atalho['id']}", headers=comum).status_code == 403
    # Alterar (inclusive trocar de categoria e de aba) e excluir
    outra = _categoria(cliente, admin, "Outra")
    r = cliente.put(f"{URL}/itens/{atalho['id']}", json={"categoria_id": outra["id"], "titulo": "Webmail", "url": "https://mail.exemplo.gov.br", "nova_aba": False}, headers=admin)
    assert r.status_code == 200 and r.json()["categoria_id"] == outra["id"] and r.json()["nova_aba"] is False
    assert cliente.delete(f"{URL}/itens/{atalho['id']}", headers=admin).status_code == 204
    assert cliente.delete(f"{URL}/itens/{atalho['id']}", headers=admin).status_code == 404


def test_validacao_do_destino_e_do_nome(cliente, admin):
    categoria = _categoria(cliente, admin)
    def tenta(url):
        return cliente.post(f"{URL}/itens", json={"categoria_id": categoria["id"], "titulo": "T", "url": url}, headers=admin).status_code
    assert [tenta(u) for u in ("javascript:alert(1)", "//evil.com", "contratos", "ftp://x.com/a", "https://", "https://a b.com")] == [422] * 6
    assert [tenta(u) for u in ("/contratos?aba=x", "http://intranet/pagina", "https://www.doe.sp.gov.br/")] == [201] * 3
    assert cliente.post(f"{URL}/itens", json={"categoria_id": 9999, "titulo": "T", "url": "/x"}, headers=admin).status_code == 404
    # Nome da categoria único sem diferenciar maiúsculas (a categoria "Sistemas" já existe)
    assert cliente.post(f"{URL}/categorias", json={"nome": "SISTEMAS"}, headers=admin).status_code == 409
    assert cliente.post(f"{URL}/categorias", json={"nome": "Outra categoria"}, headers=admin).status_code == 201
    assert cliente.post(f"{URL}/categorias", json={"nome": "   "}, headers=admin).status_code == 422


def test_excluir_categoria_leva_os_atalhos_e_a_gestao_vale_para_quem_tem_a_acl(cliente, admin, _gestao_fechada):
    criar_usuario("comum2")
    h = cabecalho(cliente, "gestor_atalhos")
    categoria = _categoria(cliente, h, "Do gestor")
    _atalho(cliente, h, categoria["id"], "Ramais", "/ramais")
    assert cliente.get(f"{URL}/gestao", headers=cabecalho(cliente, "comum2")).status_code == 403
    assert cliente.delete(f"{URL}/categorias/{categoria['id']}", headers=h).status_code == 204
    assert cliente.get(f"{URL}/gestao", headers=h).json()["categorias"] == []
