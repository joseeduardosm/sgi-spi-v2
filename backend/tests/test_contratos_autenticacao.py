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


def test_memoria_tem_folha_de_autenticacao_com_codigo_hash_e_ciencias(cliente, cenario):
    contrato, base, gestora = cenario
    pdf = _memoria(cliente, base, gestora)
    paginas = PdfReader(BytesIO(pdf)).pages
    folha = " ".join(paginas[-1].extract_text().split())
    assert "Folha de autenticação" in folha and "Memória de cálculo da medição" in folha and "Ciências registradas" in folha
    assert "Gestora Silva" in folha and re.search(r"Código de verificação [0-9A-F]{4}(-[0-9A-F]{4}){3}", folha)
    assert re.search(r"[0-9a-f]{64}", folha)  # impressão digital do conteúdo


def test_verificar_por_arquivo_e_por_codigo(cliente, cenario):
    contrato, base, gestora = cenario
    pdf = _memoria(cliente, base, gestora)
    # Arquivo idêntico ao gerado: válido, com os dados do registro
    r = cliente.post(URL, files={"arquivo": ("memoria.pdf", pdf, "application/pdf")}, headers=gestora)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["valido"] is True and corpo["documento"]["tipo"] == "Memória de cálculo da medição" and corpo["documento"]["contrato_numero"] == contrato["numero"]
    assert sorted(c["nome"] for c in corpo["documento"]["ciencias"]) == ["Fiscal Souza", "Gestora Silva"]
    # Arquivo alterado: inválido
    adulterado = cliente.post(URL, files={"arquivo": ("memoria.pdf", pdf + b"\n%alterado", "application/pdf")}, headers=gestora).json()
    assert adulterado["valido"] is False and adulterado["documento"] is None
    # Código (com ou sem hífens e em minúsculas): mostra o registro
    codigo = corpo["documento"]["codigo"]
    for variante in (codigo, codigo.replace("-", "").lower()):
        achado = cliente.get(URL, params={"codigo": variante}, headers=gestora).json()
        assert achado["valido"] is True and achado["documento"]["codigo"] == codigo
    assert cliente.get(URL, params={"codigo": "0000-0000-0000-0000"}, headers=gestora).json()["valido"] is False
