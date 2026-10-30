# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a Folha de autenticação dos PDFs gerados e a verificação por código e por arquivo.
"""Autenticação de PDFs: memória de cálculo com Folha de autenticação e `/api/contratos/verificar-documento`."""

import re
from io import BytesIO

from pypdf import PdfReader

from tests.test_contratos_retencao import _ambiente, cenario  # noqa: F401 — fixtures (medição concluída, com a memória de cálculo gerada)

URL = "/api/contratos/verificar-documento"


def _memoria(cliente, base, h) -> bytes:
    detalhe = cliente.get(base, headers=h).json()
    return cliente.get(f"{base}/arquivos/{detalhe['memorias'][-1]['arquivo']['anexo_id']}", headers=h).content


def test_memoria_e_documento_intermediario_sem_folha_de_autenticacao(cliente, cenario):
    contrato, base, gestora = cenario
    pdf = _memoria(cliente, base, gestora)
    textos = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(BytesIO(pdf)).pages)
    assert "Folha de autenticação" not in textos and "Código de verificação" not in textos


def test_verificar_so_reconhece_o_consolidado(cliente, cenario):
    contrato, base, gestora = cenario
    pdf = _memoria(cliente, base, gestora)
    # A memória (intermediária) não é autenticada: só o consolidado final tem folha e registro (ver test_contratos_execucao)
    r = cliente.post(URL, files={"arquivo": ("memoria.pdf", pdf, "application/pdf")}, headers=gestora)
    assert r.status_code == 200 and r.json()["valido"] is False and r.json()["documento"] is None
    assert cliente.get(URL, params={"codigo": "0000-0000-0000-0000"}, headers=gestora).json()["valido"] is False


def test_sem_folha_de_autenticacao_tira_so_a_folha_do_fim():
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    from app.services.contratos import servico_autenticacao
    from app.services.documentos.pdf import DocumentoPdf

    corpo = DocumentoPdf("Memória de cálculo", "Contrato 1").secao("Itens").paragrafo("conteúdo").gerar()
    folha = DocumentoPdf("Folha de autenticação", "Contrato 1").secao("Documento").paragrafo("Código de verificação").gerar()
    escritor = PdfWriter()
    for parte in (corpo, folha):
        for pagina in PdfReader(BytesIO(parte)).pages:
            escritor.add_page(pagina)
    saida = BytesIO()
    escritor.write(saida)
    completo = saida.getvalue()
    assert len(PdfReader(BytesIO(completo)).pages) == len(PdfReader(BytesIO(corpo)).pages) + len(PdfReader(BytesIO(folha)).pages)
    assert len(PdfReader(BytesIO(servico_autenticacao.sem_folha_de_autenticacao(completo))).pages) == len(PdfReader(BytesIO(corpo)).pages)
    assert servico_autenticacao.sem_folha_de_autenticacao(corpo) == corpo


def test_consolidado_aceita_pdf_com_caixa_herdada_do_no_pai():
    """PDFs como os do iLovePDF herdam a MediaBox do nó /Pages: o consolidado não pode quebrar ('NoneType' has no attribute 'get_object') e todas as páginas levam o selo."""
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, FloatObject, NameObject

    from app.services.documentos.pdf import DocumentoPdf, montar_consolidado

    gerado = DocumentoPdf("Documento", "teste").paragrafo("texto").gerar()
    escritor = PdfWriter()
    for _ in range(3):
        escritor.add_blank_page(width=595, height=842)
    raiz = escritor._root_object["/Pages"]
    raiz[NameObject("/MediaBox")] = ArrayObject([FloatObject(0), FloatObject(0), FloatObject(595), FloatObject(842)])
    for pagina in raiz["/Kids"]:
        del pagina.get_object()["/MediaBox"]  # a página passa a herdar a caixa do pai
    saida = BytesIO()
    escritor.write(saida)
    pdf = montar_consolidado([(gerado, True), (saida.getvalue(), False)])
    paginas = PdfReader(BytesIO(pdf)).pages
    assert len(paginas) >= 4 and f"Página {len(paginas)} de {len(paginas)}" in paginas[-1].extract_text()
