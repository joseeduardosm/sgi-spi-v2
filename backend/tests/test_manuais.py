# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar os manuais do BookStack lidos pelo portal (integração simulada, sem rede).

import httpx
import pytest

from app.services import servico_manuais
from tests.conftest import cabecalho, criar_usuario

BASE = "https://instrucoes.teste"
PAGINA_HTML = (
    '<h1 id="bkmrk-titulo">Título</h1><p onclick="x()">Texto <strong>forte</strong><script>alert(1)</script></p>'
    f'<img src="{BASE}/uploads/images/gallery/2026-01/foto.png" alt="foto"><img src="https://outro.site/x.png"><img src="http://10.9.9.9/uploads/images/gallery/a.png">'
    f'<p><a href="{BASE}/link/2">outra</a> <a href="http://10.9.9.9/link/2">ip</a> <a href="{BASE}/books/guia/page/segunda">por slug</a> <a href="https://externo.com/a">fora</a>'
    ' <a href="javascript:alert(1)">mau</a></p><iframe src="https://x"></iframe>'
)


def _bookstack(requisicao: httpx.Request) -> httpx.Response:
    """BookStack de mentira: um livro "Guia" com um capítulo e duas páginas, uma estante e um livro avulso."""
    caminho = requisicao.url.path
    assert requisicao.headers["Authorization"] == "Token id-teste:segredo-teste"
    json = httpx.Response
    if caminho == "/api/books" and requisicao.url.params.get("count") == "1":
        return json(200, json={"data": [], "total": 2})
    if caminho == "/api/books":
        return json(200, json={"data": [{"id": 1, "name": "Guia", "description": "Primeiros passos"}, {"id": 2, "name": "Avulso", "description": ""}], "total": 2})
    if caminho == "/api/shelves":
        return json(200, json={"data": [{"id": 7, "name": "TI", "description": ""}], "total": 1})
    if caminho == "/api/shelves/7":
        return json(200, json={"id": 7, "books": [{"id": 1, "name": "Guia"}]})
    if caminho == "/api/books/1":
        return json(200, json={"id": 1, "name": "Guia", "slug": "guia", "description": "Primeiros passos", "contents": [
            {"id": 10, "name": "Capítulo", "type": "chapter", "pages": [{"id": 1, "name": "Primeira"}, {"id": 2, "name": "Segunda"}]},
            {"id": 3, "name": "Solta", "type": "page"},
        ]})
    if caminho == "/api/pages":
        return json(200, json={"data": [{"id": 2, "slug": "segunda", "book_slug": "guia"}], "total": 1})
    if caminho == "/api/pages/1":
        return json(200, json={"id": 1, "name": "Primeira", "book_id": 1, "chapter_id": 10, "html": PAGINA_HTML, "updated_at": "2026-10-01T12:00:00.000000Z"})
    if caminho == "/api/pages/99":
        return json(404, json={"error": {"message": "Page not found"}})
    if caminho == "/api/search":
        return json(200, json={"data": [
            {"type": "page", "id": 1, "name": "Primeira", "book_id": 1, "book": {"id": 1, "name": "Guia"}, "preview_content": {"content": "veja <strong>isto</strong><script>x</script>"}},
            {"type": "bookshelf", "id": 7, "name": "TI"},
        ]})
    if caminho == "/uploads/images/gallery/2026-01/foto.png":
        return json(200, content=b"\x89PNG", headers={"content-type": "image/png"})
    return json(404)


@pytest.fixture
def manuais(cliente, admin):
    """Integração configurada (como o SuperRoot faria) e ligada ao BookStack simulado."""
    servico_manuais.TRANSPORTE = httpx.MockTransport(_bookstack)
    servico_manuais.limpar_cache()
    r = cliente.put("/api/integracao-bookstack", json={"ativo": True, "url_base": BASE, "token_id": "id-teste", "token_segredo": "segredo-teste", "livros_permitidos": "1,2"}, headers=admin)
    assert r.status_code == 200, r.text
    yield
    servico_manuais.TRANSPORTE = None
    servico_manuais.limpar_cache()


def test_configuracao_nao_expoe_o_token_e_testa_a_conexao(cliente, admin, manuais):
    corpo = cliente.get("/api/integracao-bookstack", headers=admin).json()
    assert corpo["possui_token"] and corpo["configurada"] and "segredo-teste" not in str(corpo) and "id-teste" not in str(corpo)
    teste = cliente.post("/api/integracao-bookstack/testar", headers=admin).json()
    assert teste["sucesso"] and teste["livros_visiveis"] == 2
    # Só o SuperRoot configura
    criar_usuario("comum_m")
    assert cliente.get("/api/integracao-bookstack", headers=cabecalho(cliente, "comum_m")).status_code == 403


def test_sem_configuracao_responde_503(cliente, admin):
    servico_manuais.limpar_cache()
    criar_usuario("leitor_m")
    r = cliente.get("/api/manuais", headers=cabecalho(cliente, "leitor_m"))
    assert r.status_code == 503 and r.json()["codigo"] == "manuais_indisponivel"


def test_qualquer_usuario_logado_le_estantes_livro_e_pagina(cliente, manuais):
    criar_usuario("leitor_m")
    h = cabecalho(cliente, "leitor_m")
    assert cliente.get("/api/manuais").status_code == 401
    lista = cliente.get("/api/manuais", headers=h).json()
    assert [e["nome"] for e in lista["estantes"]] == ["TI"] and lista["estantes"][0]["livros"][0]["descricao"] == "Primeiros passos"
    assert [l["nome"] for l in lista["livros_avulsos"]] == ["Avulso"]

    livro = cliente.get("/api/manuais/livros/1", headers=h).json()
    assert livro["primeira_pagina_id"] == 1 and livro["sumario"][0]["tipo"] == "capitulo" and len(livro["sumario"][0]["paginas"]) == 2

    pagina = cliente.get("/api/manuais/paginas/1", headers=h).json()
    assert pagina["anterior"] is None and pagina["proxima"]["id"] == 2 and pagina["capitulo_nome"] == "Capítulo"
    assert pagina["url_origem"] == f"{BASE}/link/1"


def test_html_da_pagina_e_sanitizado_e_reescrito(cliente, manuais):
    criar_usuario("leitor_m")
    html = cliente.get("/api/manuais/paginas/1", headers=cabecalho(cliente, "leitor_m")).json()["html"]
    for proibido in ("<script", "onclick", "<iframe", "javascript:", "outro.site", 'src="'):
        assert proibido not in html
    assert 'data-caminho="/uploads/images/gallery/2026-01/foto.png"' in html
    assert 'href="/manuais/paginas/2"' in html and html.count('href="/manuais/paginas/2"') == 3 and 'data-caminho="/uploads/images/gallery/a.png"' in html
    assert 'href="https://externo.com/a"' in html and "noopener" in html
    assert '<h1 id="bkmrk-titulo">' in html


def test_busca_imagem_e_erros(cliente, manuais):
    criar_usuario("leitor_m")
    h = cabecalho(cliente, "leitor_m")
    busca = cliente.get("/api/manuais/busca", params={"q": "isto"}, headers=h).json()["itens"]
    assert len(busca) == 1 and busca[0]["rota"] == "/manuais/paginas/1" and busca[0]["trecho"] == "veja <strong>isto</strong>"
    assert cliente.get("/api/manuais/busca", params={"q": "a"}, headers=h).json()["itens"] == []

    img = cliente.get("/api/manuais/imagem", params={"caminho": "/uploads/images/gallery/2026-01/foto.png"}, headers=h)
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    # Só /uploads/ da própria instância
    for ruim in ("/api/books", "/uploads/../.env", "//evil.com/x.png", "https://evil.com/x.png"):
        assert cliente.get("/api/manuais/imagem", params={"caminho": ruim}, headers=h).status_code == 400
    assert cliente.get("/api/manuais/paginas/99", headers=h).status_code == 404


def test_manuais_fechado_por_acl_quando_ha_regra(cliente, admin, manuais):
    liberado = criar_usuario("m_liberado")
    criar_usuario("m_negado")
    recurso = cliente.post("/api/acl/recursos", json={"nome": "Manuais", "slug": "manuais"}, headers=admin).json()
    cliente.post("/api/acl/regras", json={"recurso_id": recurso["id"], "nivel": "LEITURA", "usuarios_ids": [liberado], "setores_ids": []}, headers=admin)
    assert cliente.get("/api/manuais", headers=cabecalho(cliente, "m_negado")).status_code == 403
    assert cliente.get("/api/manuais", headers=cabecalho(cliente, "m_liberado")).status_code == 200


def test_somente_os_livros_permitidos_aparecem(cliente, admin, manuais):
    criar_usuario("leitor_m")
    h = cabecalho(cliente, "leitor_m")
    r = cliente.put("/api/integracao-bookstack", json={"ativo": True, "url_base": BASE, "livros_permitidos": "1"}, headers=admin)
    assert r.status_code == 200 and r.json()["livros_permitidos"] == "1"
    lista = cliente.get("/api/manuais", headers=h).json()
    assert [l["nome"] for e in lista["estantes"] for l in e["livros"]] == ["Guia"] and lista["livros_avulsos"] == []
    # Fora da lista: o portal responde como se o livro não existisse (e a busca também não o traz)
    assert cliente.get("/api/manuais/livros/2", headers=h).status_code == 404
    assert cliente.get("/api/manuais/livros/1", headers=h).status_code == 200
    # Valor inválido é recusado; vazio NÃO libera todos: não mostra nenhum livro
    assert cliente.put("/api/integracao-bookstack", json={"ativo": True, "url_base": BASE, "livros_permitidos": "a,b"}, headers=admin).status_code == 422
    cliente.put("/api/integracao-bookstack", json={"ativo": True, "url_base": BASE, "livros_permitidos": ""}, headers=admin)
    vazia = cliente.get("/api/manuais", headers=h).json()
    assert vazia["estantes"] == [] and vazia["livros_avulsos"] == []
    assert cliente.get("/api/manuais/livros/1", headers=h).status_code == 404
    assert cliente.get("/api/manuais/paginas/1", headers=h).status_code == 404
    assert cliente.get("/api/manuais/busca", params={"q": "isto"}, headers=h).json()["itens"] == []
