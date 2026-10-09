# Criado por José Eduardo Santana Martins
# Este arquivo serve para montar o texto da portaria de designação e exportá-lo em Word e PDF com a marca d'água "MINUTA".
"""Texto e exportação da portaria de designação de gestão e fiscalização.

O texto é o HTML da máscara já preenchido (`dados["texto_html"]`, veja `servico_portaria.montar_dados`), lido como blocos; o mesmo conteúdo sai em Word (sobre o modelo institucional `recursos/portarias/portaria.docx`, que mantém o cabeçalho) e em
PDF (reportlab). Os dois levam a marca d'água "MINUTA": a versão sem marca é a publicada, que volta ao sistema como PDF.
"""

import copy
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from lxml import etree
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.contratacoes import html_blocos
# Funções de escrita dos blocos compartilhadas com o Word/PDF de Contratações
from app.services.contratacoes.docx_exportacao import ALINHAR, _escrever_trechos, _rml, _tabela_html

RECURSOS = Path(__file__).resolve().parents[2] / "recursos" / "portarias"
FONTE = "Montserrat"
MARCA_DAGUA = "MINUTA"
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
ROTULOS_PAPEL = {
    "gestor": "Gestor",
    "gestor_suplente": "Gestor suplente",
    "fiscal_administrativo": "Fiscal administrativo",
    "fiscal_administrativo_suplente": "Fiscal administrativo suplente",
    "fiscal_tecnico": "Fiscal técnico",
    "fiscal_tecnico_suplente": "Fiscal técnico suplente",
}


def titulo(dados: dict) -> str:
    return f"Portaria {dados['sigla']} nº {dados['numero']:03d}, de {dados['exercicio']}"


def blocos(dados: dict) -> list[tuple]:
    """Blocos (parágrafos, listas e tabelas) do texto da portaria, já preenchido a partir da máscara."""
    return html_blocos.blocos(dados["texto_html"])


# --- Word ---------------------------------------------------------------------------------------

_MARCA_XML = (
    '<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:o="urn:schemas-microsoft-com:office:office"><w:pict>'
    '<v:shapetype id="_x0000_t136" coordsize="21600,21600" o:spt="136" adj="10800" path="m@7,l@8,m@5,21600l@6,21600e">'
    '<v:formulas><v:f eqn="sum #0 0 10800"/><v:f eqn="prod #0 2 1"/><v:f eqn="sum 21600 0 @1"/><v:f eqn="sum 0 0 @2"/>'
    '<v:f eqn="sum 21600 0 @3"/><v:f eqn="if @0 @3 0"/><v:f eqn="if @0 21600 @1"/><v:f eqn="if @0 0 @2"/><v:f eqn="if @0 @4 21600"/>'
    '<v:f eqn="mid @5 @6"/><v:f eqn="mid @8 @5"/><v:f eqn="mid @7 @8"/><v:f eqn="mid @6 @7"/><v:f eqn="sum @6 0 @5"/></v:formulas>'
    '<v:path textpathok="t" o:connecttype="custom" o:connectlocs="@9,0;@10,10800;@11,21600;@12,10800" o:connectangles="270,180,90,0"/>'
    '<v:textpath on="t" fitshape="t"/><v:handles><v:h position="#0,bottomRight" xrange="6629,14971"/></v:handles>'
    '<o:lock v:ext="edit" text="t" shapetype="t"/></v:shapetype>'
    '<v:shape id="MarcaDaguaMinuta" o:spid="_x0000_s2049" type="#_x0000_t136" '
    'style="position:absolute;margin-left:0;margin-top:0;width:430pt;height:140pt;rotation:315;z-index:-251658752;'
    'mso-position-horizontal:center;mso-position-horizontal-relative:margin;mso-position-vertical:center;mso-position-vertical-relative:margin" '
    'o:allowincell="f" fillcolor="#d0d0d0" stroked="f"><v:fill opacity=".5"/>'
    f'<v:textpath style="font-family:&quot;Arial&quot;;font-size:1pt" string="{MARCA_DAGUA}"/></v:shape></w:pict></w:r>'
)


def _marcar_cabecalho(cabecalho) -> None:
    """Põe a marca d'água no cabeçalho (em um parágrafo próprio, para não mexer no banner do modelo)."""
    paragrafo = cabecalho.paragraphs[0] if cabecalho.paragraphs else cabecalho.add_paragraph()
    paragrafo._p.append(etree.fromstring(_MARCA_XML))


def gerar_word(dados: dict) -> bytes:
    """Word sobre o modelo institucional (cabeçalho e página preservados), com a marca d'água "MINUTA"."""
    d = docx.Document(str(RECURSOS / "portaria.docx"))
    corpo = d.element.body
    sect = corpo.sectPr
    sect_copia = copy.deepcopy(sect) if sect is not None else None
    for filho in list(corpo):
        corpo.remove(filho)
    if sect_copia is not None:
        corpo.append(sect_copia)
    for tipo, conteudo, extra in blocos(dados):
        if tipo == "tabela":
            _tabela_html(d, conteudo)
            continue
        p = d.add_paragraph()
        p.alignment = ALINHAR.get((extra if tipo == "p" else None) or "justify", WD_ALIGN_PARAGRAPH.JUSTIFY)
        p.paragraph_format.space_after = Pt(8)
        if tipo == "li":
            p.paragraph_format.left_indent = Pt(24)
            p.add_run(f"{extra} ")
        _escrever_trechos(p, conteudo)
        for run in p.runs:
            run.font.name = FONTE
    secao = d.sections[0]
    _marcar_cabecalho(secao.header)
    if secao.different_first_page_header_footer:
        _marcar_cabecalho(secao.first_page_header)
    saida = BytesIO()
    d.save(saida)
    return saida.getvalue()


# --- PDF ----------------------------------------------------------------------------------------

def _marca_dagua_pdf(tela, _documento) -> None:
    largura, altura = A4
    tela.saveState()
    tela.setFillColorRGB(0.82, 0.82, 0.82)
    tela.setFont("Helvetica-Bold", 120)
    tela.translate(largura / 2, altura / 2)
    tela.rotate(45)
    tela.drawCentredString(0, -40, MARCA_DAGUA)
    tela.restoreState()


def gerar_pdf(dados: dict) -> bytes:
    """PDF A4 retrato com o banner institucional e a marca d'água "MINUTA"."""
    saida = BytesIO()
    documento = SimpleDocTemplate(saida, pagesize=A4, leftMargin=30 * mm, rightMargin=30 * mm, topMargin=25 * mm, bottomMargin=25 * mm,
                                  title=titulo(dados), author="Secretaria de Parcerias em Investimentos")
    largura = A4[0] - 60 * mm
    estilos = {
        "justify": ParagraphStyle("portaria", fontName="Helvetica", fontSize=10.5, leading=15, alignment=TA_JUSTIFY, spaceAfter=8),
        "center": ParagraphStyle("portaria-centro", fontName="Helvetica", fontSize=10.5, leading=15, alignment=TA_CENTER, spaceAfter=4),
        "right": ParagraphStyle("portaria-direita", fontName="Helvetica", fontSize=10.5, leading=15, alignment=TA_RIGHT, spaceAfter=8),
    }
    elementos = [Image(str(RECURSOS / "cabecalho.jpg"), width=largura, height=largura * 106 / 603), Spacer(1, 8 * mm)]
    for tipo, conteudo, extra in blocos(dados):
        if tipo == "tabela":
            linhas = [[Paragraph(_rml(c) or " ", estilos["justify"]) for c in linha] for linha in conteudo]
            if linhas:
                tabela = Table(linhas, hAlign="LEFT")
                tabela.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                elementos += [tabela, Spacer(1, 2 * mm)]
            continue
        estilo = estilos["center"] if tipo == "p" and extra == "center" else estilos["right"] if tipo == "p" and extra == "right" else estilos["justify"]
        prefixo = f"{escape(str(extra))} " if tipo == "li" else ""
        elementos.append(Paragraph(prefixo + _rml(conteudo), ParagraphStyle("li", parent=estilo, leftIndent=14) if tipo == "li" else estilo))
    documento.build(elementos, onFirstPage=_marca_dagua_pdf, onLaterPages=_marca_dagua_pdf)
    return saida.getvalue()
