# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar anexos, auditoria por campo, correlação de erros e geração de documentos.
"""Fundação do módulo de contratos: anexos, auditoria por campo, correlação de erros e documentos."""

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.core.banco import FabricaSessao
from app.core.configuracao import obter_configuracao
from app.main import app
from app.services import servico_anexos
from app.services.documentos.pdf import DocumentoPdf, mesclar_pdfs
from app.services.documentos.planilha import FORMATO_MOEDA, Aba, Coluna, gerar_planilha
from app.services.servico_anexos import ErroAnexo
from app.services.servico_auditoria import auditar_alteracoes, diferencas, historico_campos

PDF_MINIMO = DocumentoPdf("Teste").paragrafo("conteúdo").gerar()


def test_guarda_pdf_com_metadados_e_permite_download():
    with FabricaSessao() as sessao:
        anexo = servico_anexos.guardar_pdf(sessao, BytesIO(PDF_MINIMO), "Contrato Assinado.pdf", "contrato-documento", None)
        sessao.commit()
        arquivo = servico_anexos.caminho(anexo)
        assert arquivo.read_bytes() == PDF_MINIMO
        assert anexo.tamanho == len(PDF_MINIMO) and len(anexo.sha256) == 64
        assert anexo.chave_armazenamento.endswith(".pdf")
        resposta = servico_anexos.resposta_download(anexo, "Contrato Assinado - 012/2026.pdf")
        assert 'filename="Contrato_Assinado_-_012_2026.pdf"' in resposta.headers["content-disposition"]


@pytest.mark.parametrize(
    ("conteudo", "mensagem"),
    [(b"", "vazio"), (b"PK\x03\x04 arquivo zip", "PDF"), (b"%PD", "PDF")],
)
def test_recusa_arquivo_que_nao_e_pdf(conteudo, mensagem):
    with FabricaSessao() as sessao, pytest.raises(ErroAnexo, match=mensagem):
        servico_anexos.guardar_pdf(sessao, BytesIO(conteudo), "x.pdf", "teste", None)
    # Nenhum arquivo parcial fica para trás
    assert not list(servico_anexos.diretorio_anexos().rglob("*.parcial"))


def test_recusa_pdf_acima_do_limite(monkeypatch):
    monkeypatch.setattr(obter_configuracao(), "anexos_tamanho_maximo_mb", 1)
    grande = b"%PDF-" + b"0" * (1024 * 1024 + 1)
    with FabricaSessao() as sessao, pytest.raises(ErroAnexo, match="limite de 1 MB"):
        servico_anexos.guardar_pdf(sessao, BytesIO(grande), "grande.pdf", "teste", None)


def test_download_de_anexo_descartado_e_recusado():
    with FabricaSessao() as sessao:
        anexo = servico_anexos.guardar_pdf_gerado(sessao, PDF_MINIMO, "memoria.pdf", "teste", None)
        servico_anexos.descartar(anexo)
        with pytest.raises(ErroAnexo):
            servico_anexos.resposta_download(anexo)


def test_diferencas_consideram_so_campos_alterados():
    antes = {"apelido": "Limpeza", "valor": Decimal("10.50"), "inicio": date(2026, 1, 1)}
    depois = {"apelido": "Limpeza predial", "valor": Decimal("10.50"), "inicio": date(2026, 2, 1)}
    assert diferencas(antes, depois) == {
        "apelido": {"de": "Limpeza", "para": "Limpeza predial"},
        "inicio": {"de": "2026-01-01", "para": "2026-02-01"},
    }


def test_historico_por_campo_do_alvo():
    with FabricaSessao() as sessao:
        auditar_alteracoes(sessao, "root", None, "contrato.alterar", "contrato", "abc", "Contrato 001/2026", {"a": 1}, {"a": 2})
        # Sem diferença, nada é registrado
        auditar_alteracoes(sessao, "root", None, "contrato.alterar", "contrato", "abc", "Contrato 001/2026", {"a": 2}, {"a": 2})
        auditar_alteracoes(sessao, "root", None, "contrato.alterar", "contrato", "outro", "Contrato 002/2026", {"a": 1}, {"a": 3})
        sessao.commit()
        registros = historico_campos(sessao, "contrato", "abc")
        assert len(registros) == 1
        assert registros[0].dados == {"campos": {"a": {"de": 1, "para": 2}}}


def test_respostas_trazem_codigo_de_correlacao(cliente):
    resposta = cliente.get("/api/saude")
    assert len(resposta.headers["X-Correlacao"]) == 12


def test_erro_inesperado_responde_500_com_correlacao():
    def falhar() -> None:
        raise RuntimeError("detalhe interno que não pode vazar")

    app.add_api_route("/api/_teste-falha", falhar, include_in_schema=False)
    try:
        with TestClient(app, raise_server_exceptions=False) as cliente:
            resposta = cliente.get("/api/_teste-falha")
    finally:
        app.router.routes.pop()
    corpo = resposta.json()
    assert resposta.status_code == 500 and corpo["codigo"] == "erro_interno"
    assert corpo["correlacao"] == resposta.headers["X-Correlacao"]
    assert corpo["correlacao"] in corpo["detalhe"] and "interno que" not in corpo["detalhe"]


def test_pdf_institucional_e_mesclagem():
    documento = DocumentoPdf("Memória de cálculo", "Contrato 001/2026", autor="Pessoa Teste")
    documento.secao("Itens").tabela(["Item", "Valor"], [["Limpeza <b>", "R$ 1,00"]] * 80, rodape=["Total", "R$ 80,00"])
    conteudo = documento.gerar()
    leitor = PdfReader(BytesIO(conteudo))
    assert len(leitor.pages) >= 2
    texto = leitor.pages[0].extract_text()
    assert "GOVERNO DO ESTADO DE SÃO PAULO" in texto and "Memória de cálculo" in texto and "Limpeza <b>" in texto
    assert len(PdfReader(BytesIO(mesclar_pdfs([conteudo, PDF_MINIMO]))).pages) == len(leitor.pages) + 1


def test_planilha_com_formatos():
    from openpyxl import load_workbook

    conteudo = gerar_planilha(
        [Aba("Previsão", [Coluna("Competência"), Coluna("Valor", FORMATO_MOEDA)], [["05/2026", Decimal("10.5")]], titulo="Previsão", rodape=["Total", Decimal("10.5")])]
    )
    folha = load_workbook(BytesIO(conteudo))["Previsão"]
    assert folha["A1"].value == "Previsão" and folha["B4"].value == 10.5 and folha["B4"].number_format == FORMATO_MOEDA
