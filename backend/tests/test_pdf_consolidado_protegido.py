# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar que PDFs protegidos por senha não derrubam a montagem do consolidado.
from io import BytesIO

from pypdf import PdfReader, PdfWriter

from app.services.contratos.documentos_execucao import _pdf_legivel
from app.services.documentos.pdf import contar_paginas, mesclar_pdfs


def _pdf(senha_usuario: str | None) -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(200, 200)
    if senha_usuario is not None:
        escritor.encrypt(user_password=senha_usuario, owner_password="dono", algorithm="AES-128")
    saida = BytesIO()
    escritor.write(saida)
    return saida.getvalue()


def test_pdf_com_senha_vazia_abre_e_com_senha_real_e_ilegivel():
    livre = _pdf("")  # criptografado só para restringir edição: abre sem senha
    assert _pdf_legivel(livre) and contar_paginas(livre) == 1
    assert len(PdfReader(BytesIO(mesclar_pdfs([livre, _pdf(None)]))).pages) == 2
    assert _pdf_legivel(_pdf("segredo")) is False  # exige senha: fica de fora e o consolidado avisa na contracapa
