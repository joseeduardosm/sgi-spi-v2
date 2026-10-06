# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a busca global, os favoritos do menu e o anterior/próximo da carteira de contratos.
"""Navegação: busca global com ACL, favoritos por usuário e vizinhos do contrato na lista."""

from tests.apoio_contratos import criar_contrato, criar_empresa, restringir_contratos
from tests.conftest import cabecalho, criar_usuario


def _tipos(resposta) -> set[str]:
    assert resposta.status_code == 200, resposta.text
    return {i["tipo"] for i in resposta.json()["itens"]}


def test_busca_global_agrupa_modulos_e_respeita_o_acl(cliente, admin):
    empresa = criar_empresa(cliente, admin, razao="Limpatudo Serviços")["id"]
    criar_contrato(cliente, admin, empresa_id=empresa, numero="012/2026", apelido="Limpeza sede")
    criar_usuario("fulano", nome_completo="Maria Limpatudo", ramal="8123")
    # Muito curto: sem resultados
    assert cliente.get("/api/busca", params={"q": "l"}, headers=admin).json()["itens"] == []
    r = cliente.get("/api/busca", params={"q": "limpa"}, headers=admin)
    assert _tipos(r) >= {"contrato", "empresa", "pessoa"}
    empresa_achada = next(i for i in r.json()["itens"] if i["tipo"] == "empresa")
    assert empresa_achada["titulo"] == "Limpatudo Serviços" and empresa_achada["rota"] == f"/contratos/empresas/{empresa}" and "1 contrato(s)" in empresa_achada["subtitulo"]
    contrato = next(i for i in r.json()["itens"] if i["tipo"] == "contrato")
    assert contrato["titulo"].startswith("Contrato 012/2026") and contrato["rota"].startswith("/contratos/")
    pessoa = next(i for i in r.json()["itens"] if i["tipo"] == "pessoa")
    assert pessoa["rota"].startswith("/ramais?q=") and "8123" in pessoa["subtitulo"]
    # Sem ACL de contratos, o bloco de contratos some (pessoas continuam para todo usuário logado)
    restringir_contratos(cliente, admin, {criar_usuario("sem_acesso"): "LEITURA"})
    sem = cabecalho(cliente, "fulano")
    sem_acesso = _tipos(cliente.get("/api/busca", params={"q": "limpa"}, headers=sem))
    assert "contrato" not in sem_acesso and "empresa" not in sem_acesso
    assert "pessoa" in _tipos(cliente.get("/api/busca", params={"q": "limpa"}, headers=sem))
    assert cliente.get("/api/busca", params={"q": "limpa"}).status_code == 401


def test_favoritos_do_menu_por_usuario(cliente, admin):
    criar_usuario("outra")
    h = cabecalho(cliente, "outra")
    assert cliente.get("/api/favoritos", headers=h).json() == {"itens": []}
    corpo = {"itens": [{"rota": "/contratos", "rotulo": "Contratos"}, {"rota": "/ramais?q=Maria", "rotulo": "Maria"}, {"rota": "/contratos", "rotulo": "Repetida"}]}
    r = cliente.put("/api/favoritos", json=corpo, headers=h)
    assert r.status_code == 200 and [i["rota"] for i in r.json()["itens"]] == ["/contratos", "/ramais?q=Maria"]
    # Cada usuário vê só os próprios; PUT substitui a lista inteira
    assert cliente.get("/api/favoritos", headers=admin).json() == {"itens": []}
    assert cliente.put("/api/favoritos", json={"itens": [{"rota": "/tarefas", "rotulo": "Tarefas"}]}, headers=h).json()["itens"] == [{"rota": "/tarefas", "rotulo": "Tarefas"}]
    # Só rota interna; no máximo 20
    for ruim in ("https://exemplo.com", "//exemplo.com", "contratos"):
        assert cliente.put("/api/favoritos", json={"itens": [{"rota": ruim, "rotulo": "x"}]}, headers=h).status_code == 422
    muitos = {"itens": [{"rota": f"/r{i}", "rotulo": f"R{i}"} for i in range(21)]}
    assert cliente.put("/api/favoritos", json=muitos, headers=h).status_code == 422


def test_vizinhos_do_contrato_na_lista(cliente, admin):
    empresa = criar_empresa(cliente, admin)["id"]
    ids = {n: criar_contrato(cliente, admin, empresa_id=empresa, numero=n)["id"] for n in ("001/2026", "002/2026", "003/2026")}
    url = lambda n, **p: cliente.get(f"/api/contratos/{ids[n]}/vizinhos", params=p, headers=admin).json()  # noqa: E731
    # Ordem padrão (mais recente primeiro): 003, 002, 001
    meio = url("002/2026")
    assert (meio["anterior_id"], meio["proximo_id"], meio["posicao"], meio["total"]) == (ids["003/2026"], ids["001/2026"], 2, 3)
    assert url("003/2026")["anterior_id"] is None and url("001/2026")["proximo_id"] is None
    # Ordem crescente inverte os vizinhos; a busca restringe a lista
    assert url("002/2026", ordenar_por="numero", direcao="asc")["anterior_id"] == ids["001/2026"]
    fora = url("002/2026", busca="003")
    assert fora["posicao"] is None and fora["total"] == 1
