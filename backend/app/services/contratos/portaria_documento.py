"""
===============================================================================
ARQUIVO: portaria_documento.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Montar o texto da portaria de designação de gestão e fiscalização e gerar
os dois PDFs do fluxo: a minuta (com marca d'água) e a evidência das
ciências e do aceite.

RESUMO TÉCNICO:
O texto é o HTML da máscara já preenchido (`dados["texto_html"]`, montado
por `servico_portaria.montar_dados`): a tela o mostra com botão copiar,
como o despacho da última etapa da execução; não há minuta em Word.
`gerar_minuta` converte esse HTML em elementos do ReportLab (`_flowables`)
com a marca d'água "MINUTA"; `gerar_evidencia` monta um PDF com função,
nomeado e data da ciência de cada designado, mais o aceite da autoridade.

FINALIDADE DE NEGÓCIO:
A portaria nomeia gestor e fiscais do contrato. A minuta vai anexa ao
e-mail que pede o aceite da autoridade; a evidência é juntada ao processo
SEI antes da publicação no Diário Oficial (D.O.E.), comprovando que todos
tomaram ciência. A designação só vale no sistema após a publicação.

CONTEXTO NO SISTEMA:
Usado por `servico_portaria` (fluxo da portaria no contrato). Converte o HTML
com `contratacoes.html_blocos` e gera o PDF com `documentos.pdf.DocumentoPdf`.

===============================================================================
"""

from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle

from app.services.contratacoes import html_blocos
from app.services.contratacoes.html_blocos import Trecho
from app.services.documentos.pdf import ESTILO_TEXTO, FUSO_SAO_PAULO, DocumentoPdf

# Nomes dos meses por extenso (datas no texto da portaria)
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
# Papel técnico na equipe do contrato → rótulo exibido no PDF de evidência
ROTULOS_PAPEL = {
    "gestor": "Gestor",
    "gestor_suplente": "Gestor suplente",
    "fiscal_administrativo": "Fiscal administrativo",
    "fiscal_administrativo_suplente": "Fiscal administrativo suplente",
    "fiscal_tecnico": "Fiscal técnico",
    "fiscal_tecnico_suplente": "Fiscal técnico suplente",
}
# Orientação impressa no fim da evidência (o que fazer com o documento)
RODAPE_EVIDENCIA = (
    "Este documento deverá ser juntado ao processo SEI como evidência da ciência dos servidores designados e do aceite da autoridade "
    "competente, para que, em seguida, seja providenciada a publicação da portaria no Diário Oficial do Estado (D.O.E.). "
    "A designação produz efeitos no sistema somente após a comprovação da publicação, anexada pelo Protocolo."
)


def titulo(dados: dict) -> str:
    """Título da portaria, ex.: "Portaria SPI SSGC nº 015, de 2026" (número com 3 dígitos)."""
    return f"Portaria {dados['sigla']} nº {dados['numero']:03d}, de {dados['exercicio']}"


def blocos(dados: dict) -> list[tuple]:
    """Blocos (parágrafos, listas e tabelas) do texto da portaria, já preenchido a partir da máscara."""
    return html_blocos.blocos(dados["texto_html"])


def _data_hora(instante: datetime | None) -> str:
    """Data e hora no horário de São Paulo ("dd/mm/aaaa às hh:mm"); sem data, travessão."""
    return instante.astimezone(FUSO_SAO_PAULO).strftime("%d/%m/%Y às %H:%M") if instante else "—"


def gerar_evidencia(dados: dict, contrato_rotulo: str, nomeacoes: list[dict], autoridade: dict, solicitante: str, gerado_por: str) -> bytes:
    """PDF de evidência. `nomeacoes` = [{papel, nome, ciente_em}]; `autoridade` = {nome, cargo, aceita_em}.

    Também recebe o rótulo do contrato, quem elaborou a portaria (`solicitante`) e
    quem gerou o arquivo (`gerado_por`, gravado como autor do PDF). Devolve os
    bytes do PDF; não grava nada (quem chama decide onde anexar).
    """
    documento = DocumentoPdf(titulo=f"Evidência de ciência e aceite — {titulo(dados)}", subtitulo=contrato_rotulo, paisagem=False, autor=gerado_por)
    documento.campos([
        ("Portaria", titulo(dados)), ("Contrato", contrato_rotulo),
        ("Empresa", dados.get("empresa", "")), ("Processo SEI", dados.get("processo_sei", "")),
        ("Portaria elaborada por", solicitante), ("Número reservado", f"{dados['numero']:03d}/{dados['exercicio']}"),
    ])
    documento.secao("Ciência dos designados")
    documento.tabela(
        ["Função", "Designado", "Ciência"],
        [[ROTULOS_PAPEL.get(n["papel"], n["papel"]), n["nome"], _data_hora(n["ciente_em"])] for n in nomeacoes],
        larguras=[3, 4, 3],
    )
    documento.secao("Aceite da autoridade competente")
    documento.tabela(
        ["Função", "Autoridade", "Aceite"],
        [[autoridade["cargo"] or "Autoridade competente", autoridade["nome"], _data_hora(autoridade["aceita_em"])]],
        larguras=[3, 4, 3],
    )
    documento.espaco(6)
    documento.paragrafo(RODAPE_EVIDENCIA)
    return documento.gerar()


# --- Minuta (texto da portaria com marca d'água) -------------------------------------------------

# Alinhamento do HTML (text-align) → constante do ReportLab
_ALINHAMENTO = {"center": TA_CENTER, "right": TA_RIGHT, "justify": TA_JUSTIFY, "left": TA_LEFT}


def _marcado(trechos: list[Trecho]) -> str:
    """Trechos formatados → marcação do ReportLab (negrito, itálico, sublinhado), com o texto escapado."""
    partes = []
    # O texto é escapado primeiro (evita que "<" ou "&" quebrem o PDF) e depois recebe as tags de formatação
    for t in trechos:
        texto = escape(t.texto).replace("\n", "<br/>")
        if t.negrito:
            texto = f"<b>{texto}</b>"
        if t.italico:
            texto = f"<i>{texto}</i>"
        if t.sublinhado:
            texto = f"<u>{texto}</u>"
        partes.append(texto)
    return "".join(partes)


def _flowables(blocos_texto: list[tuple]) -> list:
    """Blocos do HTML da portaria (parágrafos, itens e tabelas) → elementos do PDF."""
    saida = []
    # Cada bloco é (tipo, conteúdo, extra): "p" = parágrafo (extra = alinhamento),
    # "li" = item de lista (extra = marcador ou número), "tabela" = linhas de células
    for tipo, conteudo, extra in blocos_texto:
        if tipo == "p":
            estilo = ParagraphStyle("portaria", parent=ESTILO_TEXTO, alignment=_ALINHAMENTO.get(extra or "", TA_JUSTIFY), spaceAfter=6, leading=14)
            saida.append(Paragraph(_marcado(conteudo), estilo))
        elif tipo == "li":
            estilo = ParagraphStyle("portaria_item", parent=ESTILO_TEXTO, leftIndent=14, spaceAfter=3, leading=14)
            saida.append(Paragraph(f"{escape(str(extra or '•'))} {_marcado(conteudo)}", estilo))
        elif tipo == "tabela":
            linhas = [[Paragraph(_marcado(celula), ESTILO_TEXTO) for celula in linha] for linha in conteudo]
            tabela = Table(linhas)
            tabela.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, "#c5cad0"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            saida.append(tabela)
    return saida


def gerar_minuta(dados: dict, contrato_rotulo: str, gerado_por: str) -> bytes:
    """PDF da minuta da portaria: o texto (da máscara já preenchida) com a marca d'água MINUTA ao fundo, para a autoridade conferir antes do aceite."""
    documento = DocumentoPdf(titulo=f"Minuta — {titulo(dados)}", subtitulo=contrato_rotulo, paisagem=False, autor=gerado_por, marca_dagua="MINUTA")
    documento.blocos.extend(_flowables(blocos(dados)))
    return documento.gerar()
