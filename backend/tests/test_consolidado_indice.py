# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o índice com hiperlinks na primeira página do documento consolidado.
"""Consolidado: o índice é a primeira página e cada documento tem um hiperlink que leva à sua página."""

from io import BytesIO

from pypdf import PdfReader
from reportlab.platypus import PageBreak

from app.services.documentos.pdf import DocumentoPdf, EntradaIndice, contar_paginas, indice_consolidado, montar_consolidado


def _documento(titulo: str, paginas: int) -> bytes:
    """PDF de teste com `paginas` páginas."""
    doc = DocumentoPdf(titulo)
    for n in range(paginas):
        doc.paragrafo(f"{titulo} · parte {n + 1}")
        if n < paginas - 1:
            doc.bloco(PageBreak())
    return doc.gerar()


def _montar(quantidade: int):
    """Monta um consolidado com `quantidade` documentos de 2 páginas, refazendo o índice até estabilizar (como o serviço)."""
    partes = [(_documento(f"Documento {n}", 2), True) for n in range(1, quantidade + 1)]
    deslocamento = 1
    while True:
        entradas = [EntradaIndice(str(n), "Etapa", f"Documento {n}", 2 * (n - 1) + 1 + deslocamento, 2 * n + deslocamento) for n in range(1, quantidade + 1)]
        indice, links = indice_consolidado("Índice do documento consolidado", "Contrato 001/2026 · Competência 01/2026", entradas)
        if contar_paginas(indice) == deslocamento:
            break
        deslocamento = contar_paginas(indice)
    marcadores = [(f"{e.numero}. {e.titulo}", e.pagina_inicial) for e in entradas]
    return montar_consolidado([(indice, True), *partes], links=links, marcadores=marcadores), deslocamento, entradas


def _destinos(leitor: PdfReader) -> dict[int, list[int]]:
    """Página (1-based) → páginas de destino dos links dela."""
    saida: dict[int, list[int]] = {}
    for numero, pagina in enumerate(leitor.pages, start=1):
        for anotacao in pagina.get("/Annots", []) or []:
            anotacao = anotacao.get_object()
            if anotacao.get("/Subtype") == "/Link":
                destino = anotacao["/Dest"][0].get_object()
                saida.setdefault(numero, []).append(next(i for i, p in enumerate(leitor.pages, start=1) if p.indirect_reference == destino.indirect_reference))
    return saida


def test_indice_e_a_primeira_pagina_e_os_links_levam_ao_documento():
    pdf, deslocamento, entradas = _montar(3)
    leitor = PdfReader(BytesIO(pdf))
    assert deslocamento == 1 and len(leitor.pages) == 1 + 6
    assert "Índice do documento consolidado" in leitor.pages[0].extract_text()
    # Dois links por documento (título e páginas), todos para a primeira página do documento
    destinos = _destinos(leitor)[1]
    assert sorted(destinos) == sorted([e.pagina_inicial for e in entradas for _ in range(2)])
    assert "Documento 2" in leitor.pages[entradas[1].pagina_inicial - 1].extract_text()
    assert [m.title for m in leitor.outline] == ["1. Documento 1", "2. Documento 2", "3. Documento 3"]


def test_indice_longo_ocupa_varias_paginas_e_os_destinos_acompanham():
    pdf, deslocamento, entradas = _montar(40)
    leitor = PdfReader(BytesIO(pdf))
    assert deslocamento >= 2 and len(leitor.pages) == deslocamento + 80
    todos = [d for lista in _destinos(leitor).values() for d in lista]
    assert len(todos) == 80
    # O link do último documento cai na página dele, já deslocada pelas páginas do índice
    ultimo = entradas[-1].pagina_inicial
    assert ultimo == 2 * 39 + 1 + deslocamento and "Documento 40" in leitor.pages[ultimo - 1].extract_text()
