# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a tabela simples (`| a | b |`) no corpo dos e-mails da mensageria.
"""Corpo de e-mail: linhas com barras viram tabela HTML (cabeçalho, linhas e escape de HTML)."""

from app.services import modelo_email


def test_linhas_com_barras_viram_tabela_html():
    html = modelo_email.corpo_html("Resumo\n\n| Nº | Título |\n| --- | --- |\n| #1 | <b>x</b> |\n\nFim")
    assert html.count("<table") == 1 and html.count("<tr>") == 2  # cabeçalho + 1 linha (a linha de traços é ignorada)
    assert "<th" in html and ">#1</td>" in html and "&lt;b&gt;x&lt;/b&gt;" in html
    assert html.index("Resumo") < html.index("<table") < html.index("Fim")
