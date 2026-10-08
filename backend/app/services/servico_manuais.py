# Criado por José Eduardo Santana Martins
# Este arquivo serve para ler os manuais do BookStack (estantes, livros, páginas, busca e imagens) com cache curto.
"""Manuais do BookStack lidos pelo portal.

O portal usa uma conta de serviço só de leitura (token cifrado em `integracao_bookstack`). Listas, sumários e páginas ficam em
cache em memória por alguns minutos, para não sobrecarregar o BookStack; salvar a configuração limpa o cache.
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.core.erros import ErroApi
from app.schemas.manuais import (
    DetalheLivro, DetalhePagina, Estante, ItemSumario, ListaManuais, PaginaVizinha, ResultadoBuscaManual, ResultadoBuscaManuais, ResumoLivro,
)
from app.services import servico_integracao_bookstack as integracao
from app.services.bookstack.cliente_bookstack import ClienteBookstack, ErroBookstack
from app.services.bookstack.sanitizacao import caminho_imagem_valido, preparar_html, trecho_seguro

# Transporte HTTP alternativo (os testes trocam por `httpx.MockTransport`); em produção é `None`
TRANSPORTE = None
# Segundos que listas, sumários e páginas ficam em cache
VALIDADE_CACHE = 300
_cache: dict[tuple, tuple[float, object]] = {}


def limpar_cache() -> None:
    """Descarta tudo (ao salvar a configuração ou nos testes)."""
    _cache.clear()


def _cacheado(chave: tuple, produzir: Callable[[], object]):
    """Valor em cache (se ainda válido) ou o produzido agora."""
    agora = time.monotonic()
    guardado = _cache.get(chave)
    if guardado and guardado[0] > agora:
        return guardado[1]
    valor = produzir()
    _cache[chave] = (agora + VALIDADE_CACHE, valor)
    return valor


@contextmanager
def _bookstack(sessao: Session) -> Iterator[ClienteBookstack]:
    """Cliente do BookStack pela configuração gravada; erros viram respostas da API (503 sem configuração, 404, 502)."""
    config = integracao.obter(sessao)
    if not (config.ativo and config.url_base and config.token_id_cifrado and config.token_segredo_cifrado):
        raise ErroApi(status.HTTP_503_SERVICE_UNAVAILABLE, "Os manuais ainda não foram configurados. Avise o administrador.", "manuais_indisponivel")
    try:
        token_id, segredo = integracao.tokens(config)
        with ClienteBookstack(config.url_base, token_id, segredo, TRANSPORTE) as cliente:
            yield cliente
    except ErroBookstack as erro:
        if erro.nao_encontrado:
            raise ErroApi(status.HTTP_404_NOT_FOUND, erro.mensagem, "nao_encontrado") from erro
        raise ErroApi(status.HTTP_502_BAD_GATEWAY, erro.mensagem, "bookstack_indisponivel") from erro


def _url_base(sessao: Session) -> str:
    return integracao.obter(sessao).url_base


def _permitidos(sessao: Session) -> set[int]:
    """Ids dos únicos livros que o portal mostra (configuração). Falha fechada: lista vazia = nenhum livro (nunca "todos")."""
    return {int(p) for p in integracao.obter(sessao).livros_permitidos.split(",") if p.strip().isdigit()}


def _exigir_livro(sessao: Session, livro_id: int) -> None:
    """404 para livro fora da lista permitida (o portal age como se ele não existisse)."""
    if livro_id not in _permitidos(sessao):
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Conteúdo não encontrado no BookStack.", "nao_encontrado")


def _resumo(livro: dict) -> ResumoLivro:
    return ResumoLivro(id=livro["id"], nome=livro.get("name", ""), descricao=(livro.get("description") or "").strip())


def listar(sessao: Session) -> ListaManuais:
    """Estantes com seus livros e os livros sem estante, em ordem alfabética."""
    def produzir() -> ListaManuais:
        with _bookstack(sessao) as bookstack:
            permitidos = _permitidos(sessao)
            livros = {l["id"]: l for l in bookstack.listar("/books") if l["id"] in permitidos}
            estantes: list[Estante] = []
            em_estante: set[int] = set()
            for estante in bookstack.listar("/shelves"):
                detalhe = bookstack.obter(f"/shelves/{estante['id']}")
                dela = [l for l in detalhe.get("books", []) if l["id"] in livros]
                em_estante.update(l["id"] for l in dela)
                # Estantes sem nenhum livro permitido somem
                if not dela:
                    continue
                estantes.append(Estante(
                    id=estante["id"], nome=estante.get("name", ""), descricao=(estante.get("description") or "").strip(),
                    livros=[_resumo(livros[l["id"]]) for l in dela],
                ))
            avulsos = sorted((_resumo(l) for i, l in livros.items() if i not in em_estante), key=lambda l: l.nome.casefold())
            return ListaManuais(estantes=sorted(estantes, key=lambda e: e.nome.casefold()), livros_avulsos=avulsos, url_origem=bookstack.base)
    return _cacheado(("lista", _url_base(sessao)), produzir)  # type: ignore[return-value]


def _sumario(conteudo: list[dict]) -> list[ItemSumario]:
    """Árvore (capítulos com páginas e páginas soltas) na ordem do livro."""
    itens = []
    for entrada in conteudo:
        if entrada.get("type") == "chapter":
            itens.append(ItemSumario(tipo="capitulo", id=entrada["id"], nome=entrada.get("name", ""),
                                     paginas=[ItemSumario(tipo="pagina", id=p["id"], nome=p.get("name", "")) for p in entrada.get("pages", [])]))
        else:
            itens.append(ItemSumario(tipo="pagina", id=entrada["id"], nome=entrada.get("name", "")))
    return itens


def _ordem_leitura(sumario: list[ItemSumario]) -> list[ItemSumario]:
    """Só as páginas, na ordem de leitura."""
    ordem: list[ItemSumario] = []
    for item in sumario:
        ordem.extend(item.paginas if item.tipo == "capitulo" else [item])
    return ordem


def livro(sessao: Session, livro_id: int) -> DetalheLivro:
    """Sumário de um livro."""
    def produzir() -> DetalheLivro:
        _exigir_livro(sessao, livro_id)
        with _bookstack(sessao) as bookstack:
            dados = bookstack.obter(f"/books/{livro_id}")
            sumario = _sumario(dados.get("contents", []))
            paginas = _ordem_leitura(sumario)
            return DetalheLivro(id=dados["id"], nome=dados.get("name", ""), descricao=(dados.get("description") or "").strip(), sumario=sumario,
                                primeira_pagina_id=paginas[0].id if paginas else None, url_origem=f"{bookstack.base}/books/{dados.get('slug', '')}")
    return _cacheado(("livro", _url_base(sessao), livro_id), produzir)  # type: ignore[return-value]


def _mapa_paginas(sessao: Session) -> dict[tuple[str, str], int]:
    """(slug do livro, slug da página) → id, para trocar links do BookStack por links do portal."""
    def produzir() -> dict[tuple[str, str], int]:
        with _bookstack(sessao) as bookstack:
            return {(p["book_slug"], p["slug"]): p["id"] for p in bookstack.listar("/pages") if p.get("book_slug") and p.get("slug")}
    try:
        return _cacheado(("mapa", _url_base(sessao)), produzir)  # type: ignore[return-value]
    except ErroApi:
        # O mapa só melhora links; sem ele a página abre do mesmo jeito
        return {}


def pagina(sessao: Session, pagina_id: int) -> DetalhePagina:
    """Página com o HTML sanitizado, o caminho (livro/capítulo) e a anterior/próxima na ordem de leitura."""
    def produzir() -> DetalhePagina:
        with _bookstack(sessao) as bookstack:
            dados = bookstack.obter(f"/pages/{pagina_id}")
            base = bookstack.base
        _exigir_livro(sessao, dados["book_id"])
        detalhe_livro = livro(sessao, dados["book_id"])
        ordem = _ordem_leitura(detalhe_livro.sumario)
        posicao = next((i for i, p in enumerate(ordem) if p.id == pagina_id), None)
        capitulo = next((c for c in detalhe_livro.sumario if c.tipo == "capitulo" and any(p.id == pagina_id for p in c.paginas)), None)
        vizinha = lambda p: PaginaVizinha(id=p.id, nome=p.nome)  # noqa: E731
        atualizado = dados.get("updated_at")
        return DetalhePagina(
            id=dados["id"], nome=dados.get("name", ""), livro_id=detalhe_livro.id, livro_nome=detalhe_livro.nome,
            capitulo_id=capitulo.id if capitulo else None, capitulo_nome=capitulo.nome if capitulo else None,
            html=preparar_html(dados.get("html", ""), base, _mapa_paginas(sessao)),
            atualizado_em=datetime.fromisoformat(atualizado.replace("Z", "+00:00")) if atualizado else None,
            anterior=vizinha(ordem[posicao - 1]) if posicao else None,
            proxima=vizinha(ordem[posicao + 1]) if posicao is not None and posicao + 1 < len(ordem) else None,
            url_origem=f"{base}/link/{dados['id']}",
        )
    return _cacheado(("pagina", _url_base(sessao), pagina_id), produzir)  # type: ignore[return-value]


def buscar(sessao: Session, termo: str) -> ResultadoBuscaManuais:
    """Busca do próprio BookStack (páginas, capítulos e livros); sem cache."""
    termo = (termo or "").strip()
    if len(termo) < 2:
        return ResultadoBuscaManuais(itens=[])
    with _bookstack(sessao) as bookstack:
        resposta = bookstack.obter("/search", {"query": termo, "count": 30})
    itens: list[ResultadoBuscaManual] = []
    permitidos = _permitidos(sessao)
    for achado in resposta.get("data", []) if isinstance(resposta, dict) else []:
        tipo = {"page": "pagina", "chapter": "capitulo", "book": "livro"}.get(achado.get("type"))
        if not tipo:
            continue
        livro_dados = achado.get("book") or {}
        livro_id = achado["id"] if tipo == "livro" else achado.get("book_id")
        # Resultados de livros fora da lista permitida não aparecem
        if livro_id not in permitidos:
            continue
        rota = f"/manuais/paginas/{achado['id']}" if tipo == "pagina" else f"/manuais/livros/{livro_id}"
        previa = achado.get("preview_content") or {}
        itens.append(ResultadoBuscaManual(
            tipo=tipo, id=achado["id"], nome=achado.get("name", ""), livro_id=livro_id, livro_nome=livro_dados.get("name"),
            trecho=trecho_seguro(previa.get("content", "") if isinstance(previa, dict) else ""), rota=rota,
        ))
    return ResultadoBuscaManuais(itens=itens)


def imagem(sessao: Session, caminho: str) -> tuple[bytes, str]:
    """Imagem do BookStack repassada ao navegador. Só `/uploads/...` da própria instância (nada de `..`, esquemas ou outros diretórios)."""
    if not caminho_imagem_valido(caminho):
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "Caminho de imagem inválido.", "invalido")
    with _bookstack(sessao) as bookstack:
        return bookstack.baixar_imagem(caminho)
