# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a configuração do menu lateral: leitura aberta, gravação por ACL, validações e restauração do padrão.
"""`/api/menu`: qualquer usuário lê; gravar e restaurar exige o recurso `atalhos` ≥ MODIFICACAO."""

from tests.conftest import cabecalho, criar_usuario

BASE = "/api/menu"


def _no(id_, tipo="modulo", **extra):
    return {"id": id_, "tipo": tipo, **extra}


def test_sem_configuracao_vale_o_padrao_e_todos_leem(cliente, admin):
    criar_usuario("comum-menu", nome_completo="Comum")
    r = cliente.get(BASE, headers=cabecalho(cliente, "comum-menu"))
    assert r.status_code == 200 and r.json()["padrao"] is True and r.json()["itens"] == []


def test_gravar_ler_e_restaurar(cliente, admin):
    corpo = {"itens": [
        _no("inicio"),
        _no("g-1", "grupo", rotulo="Gestão de pessoas"),
        _no("rh", pai_id="g-1", rotulo="Recursos Humanos"),
        _no("l-1", "link", rotulo="Portal", url="https://portal.exemplo.gov.br", pai_id="g-1"),
        _no("l-2", "link", rotulo="Ramais", url="/ramais?q=a"),
        _no("sla-prazos", oculto=True),
    ]}
    r = cliente.put(BASE, json=corpo, headers=admin)
    assert r.status_code == 200, r.text
    lido = cliente.get(BASE, headers=admin).json()
    assert lido["padrao"] is False and [n["id"] for n in lido["itens"]] == ["inicio", "g-1", "rh", "l-1", "l-2", "sla-prazos"]
    assert lido["itens"][5]["oculto"] is True and lido["atualizado_por_nome"]
    assert cliente.delete(BASE, headers=admin).status_code == 204
    assert cliente.get(BASE, headers=admin).json()["padrao"] is True


def test_validacoes_da_estrutura(cliente, admin):
    def gravar(itens):
        return cliente.put(BASE, json={"itens": itens}, headers=admin).status_code

    assert gravar([_no("a"), _no("a")]) == 422  # repetido
    assert gravar([_no("a", pai_id="nao-existe")]) == 422  # grupo inexistente
    assert gravar([_no("a", pai_id="a")]) == 422  # pai de si mesmo
    assert gravar([_no("g", "grupo", rotulo="G"), _no("h", "grupo", rotulo="H", pai_id="g"), _no("a", pai_id="h")]) == 422  # três níveis
    assert gravar([_no("l", "link", rotulo="L", url="x"), ]) == 422  # endereço inválido
    assert gravar([_no("l", "link", rotulo="L", url="javascript:alert(1)")]) == 422
    assert gravar([_no("l", "link", rotulo="L", url="//mal.com")]) == 422
    assert gravar([_no("g", "grupo")]) == 422  # grupo sem nome
    assert gravar([_no("l", "link", rotulo="L", url="/a"), _no("m", pai_id="l")]) == 422  # link não contém itens
    assert gravar([_no("m", url="/a")]) == 422  # módulo não tem endereço
    assert gravar([_no("g", "grupo", rotulo="G"), _no("l", "link", rotulo="L", url="/a", pai_id="g")]) == 200


def test_gravar_exige_acl_atalhos(cliente, admin):
    criar_usuario("comum-menu2", nome_completo="Comum 2")
    gestor = criar_usuario("gestor-menu", nome_completo="Gestor do menu")
    recurso = cliente.post("/api/acl/recursos", json={"nome": "Atalhos", "slug": "atalhos"}, headers=admin).json()["id"]
    cliente.post("/api/acl/regras", json={"recurso_id": recurso, "nivel": "MODIFICACAO", "usuarios_ids": [gestor], "setores_ids": []}, headers=admin)
    comum = cabecalho(cliente, "comum-menu2")
    assert cliente.put(BASE, json={"itens": []}, headers=comum).status_code == 403
    assert cliente.delete(BASE, headers=comum).status_code == 403
    assert cliente.put(BASE, json={"itens": []}, headers=cabecalho(cliente, "gestor-menu")).status_code == 200
