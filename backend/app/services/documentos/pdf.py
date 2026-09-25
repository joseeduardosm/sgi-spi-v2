"""Geração de PDFs com a identidade do Governo de SP (brasão e vermelho institucional).

Os documentos são montados com blocos simples (títulos, parágrafos, pares rótulo/valor e
tabelas) para que cada módulo descreva só o conteúdo, sem repetir estilo nem paginação.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

CAMINHO_BRASAO = Path(__file__).resolve().parents[2] / "recursos" / "brasao.png"
FUSO_SAO_PAULO = ZoneInfo("America/Sao_Paulo")

VERMELHO = colors.HexColor("#c82331")
VERMELHO_SUAVE = colors.HexColor("#fcecee")
TEXTO = colors.HexColor("#18222e")
APAGADO = colors.HexColor("#586372")
BORDA = colors.HexColor("#e2e5e8")

_base = getSampleStyleSheet()
ESTILO_TEXTO = ParagraphStyle("texto", parent=_base["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=TEXTO)
ESTILO_PEQUENO = ParagraphStyle("pequeno", parent=ESTILO_TEXTO, fontSize=8, leading=10)
ESTILO_PEQUENO_DIREITA = ParagraphStyle("pequeno_direita", parent=ESTILO_PEQUENO, alignment=TA_RIGHT)
ESTILO_ROTULO = ParagraphStyle("rotulo", parent=ESTILO_PEQUENO, textColor=APAGADO)
ESTILO_TITULO = ParagraphStyle("titulo", parent=ESTILO_TEXTO, fontName="Helvetica-Bold", fontSize=14, leading=18, spaceAfter=2)
ESTILO_SUBTITULO = ParagraphStyle("subtitulo", parent=ESTILO_TEXTO, textColor=APAGADO, spaceAfter=6)
ESTILO_SECAO = ParagraphStyle(
    "secao", parent=ESTILO_TEXTO, fontName="Helvetica-Bold", fontSize=10.5, textColor=VERMELHO, spaceBefore=10, spaceAfter=4
)


def texto(conteudo: str, estilo: ParagraphStyle = ESTILO_TEXTO) -> Paragraph:
    """Parágrafo com o conteúdo escapado (o texto do usuário nunca vira marcação)."""
    return Paragraph(escape(conteudo or "").replace("\n", "<br/>"), estilo)


@dataclass
class DocumentoPdf:
    """Documento em construção. Use os métodos para empilhar blocos e `gerar()` no final."""

    titulo: str
    subtitulo: str = ""
    paisagem: bool = False
    autor: str = ""
    blocos: list[Flowable] = field(default_factory=list)

    def secao(self, titulo: str) -> "DocumentoPdf":
        self.blocos.append(Paragraph(escape(titulo), ESTILO_SECAO))
        return self

    def paragrafo(self, conteudo: str) -> "DocumentoPdf":
        self.blocos.append(texto(conteudo))
        return self

    def espaco(self, altura_mm: float = 4) -> "DocumentoPdf":
        self.blocos.append(Spacer(1, altura_mm * mm))
        return self

    def campos(self, pares: Sequence[tuple[str, str]], colunas: int = 2) -> "DocumentoPdf":
        """Pares rótulo/valor distribuídos em colunas (ex.: dados do contrato)."""
        celulas = [[texto(rotulo, ESTILO_ROTULO), texto(valor or "—")] for rotulo, valor in pares]
        linhas = [sum(celulas[i : i + colunas], []) for i in range(0, len(celulas), colunas)]
        if linhas and len(linhas[-1]) < colunas * 2:
            linhas[-1] += [""] * (colunas * 2 - len(linhas[-1]))
        largura = self._largura_util() / colunas
        tabela = Table(linhas, colWidths=[largura * 0.35, largura * 0.65] * colunas)
        tabela.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        self.blocos.append(tabela)
        return self

    def tabela(
        self,
        cabecalho: Sequence[str],
        linhas: Iterable[Sequence[str]],
        larguras: Sequence[float] | None = None,
        alinhar_direita: Iterable[int] = (),
        rodape: Sequence[str] | None = None,
    ) -> "DocumentoPdf":
        """Tabela com cabeçalho vermelho claro, linhas zebradas e rodapé opcional em negrito.

        `larguras` são proporções (somam qualquer valor); `alinhar_direita` são índices de coluna.
        """
        direita = set(alinhar_direita)

        def celula(valor: str, indice: int, negrito: bool = False) -> Paragraph:
            estilo = ESTILO_PEQUENO_DIREITA if indice in direita else ESTILO_PEQUENO
            conteudo = escape(valor or "")
            return Paragraph(f"<b>{conteudo}</b>" if negrito else conteudo, estilo)

        dados = [[celula(c, i, True) for i, c in enumerate(cabecalho)]]
        dados += [[celula(str(v), i) for i, v in enumerate(linha)] for linha in linhas]
        if rodape:
            dados.append([celula(str(v), i, True) for i, v in enumerate(rodape)])
        util = self._largura_util()
        proporcoes = larguras or [1] * len(cabecalho)
        total = sum(proporcoes)
        tabela = Table(dados, colWidths=[util * p / total for p in proporcoes], repeatRows=1)
        estilos = [
            ("BACKGROUND", (0, 0), (-1, 0), VERMELHO_SUAVE),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, VERMELHO),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, BORDA),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        if rodape:
            estilos.append(("LINEABOVE", (0, -1), (-1, -1), 0.8, TEXTO))
        tabela.setStyle(TableStyle(estilos))
        self.blocos.append(tabela)
        return self

    def assinaturas(self, pessoas: Sequence[tuple[str, str]]) -> "DocumentoPdf":
        """Linhas de assinatura (nome, papel), duas por linha."""
        celulas = [texto(f"______________________________\n{nome}\n{papel}", ESTILO_PEQUENO) for nome, papel in pessoas]
        linhas = [celulas[i : i + 2] + [""] * (2 - len(celulas[i : i + 2])) for i in range(0, len(celulas), 2)]
        if linhas:
            tabela = Table(linhas, colWidths=[self._largura_util() / 2] * 2)
            tabela.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 18)]))
            self.blocos.append(KeepTogether([Spacer(1, 6 * mm), tabela]))
        return self

    def _tamanho(self) -> tuple[float, float]:
        return landscape(A4) if self.paisagem else A4

    def _largura_util(self) -> float:
        return self._tamanho()[0] - 30 * mm

    def _desenhar_moldura(self, tela, documento) -> None:
        """Cabeçalho (brasão + órgão + filete vermelho) e rodapé (geração e página) de cada página."""
        largura, altura = self._tamanho()
        tela.saveState()
        topo = altura - 12 * mm
        if CAMINHO_BRASAO.is_file():
            # Proporção original do brasão: 1921 x 1081
            tela.drawImage(str(CAMINHO_BRASAO), 15 * mm, topo - 11 * mm, width=19.5 * mm, height=11 * mm, mask="auto")
        tela.setFillColor(TEXTO)
        tela.setFont("Helvetica-Bold", 10)
        tela.drawString(38 * mm, topo - 4 * mm, "GOVERNO DO ESTADO DE SÃO PAULO")
        tela.setFont("Helvetica", 8.5)
        tela.setFillColor(APAGADO)
        tela.drawString(38 * mm, topo - 8.5 * mm, "Secretaria de Parcerias em Investimentos")
        tela.setStrokeColor(VERMELHO)
        tela.setLineWidth(1.4)
        tela.line(15 * mm, topo - 14 * mm, largura - 15 * mm, topo - 14 * mm)

        agora = datetime.now(FUSO_SAO_PAULO).strftime("%d/%m/%Y %H:%M")
        tela.setFont("Helvetica", 7.5)
        tela.setFillColor(APAGADO)
        rodape = f"Gerado em {agora}" + (f" por {self.autor}" if self.autor else "")
        tela.drawString(15 * mm, 9 * mm, rodape)
        tela.drawRightString(largura - 15 * mm, 9 * mm, f"Página {documento.page}")
        tela.restoreState()

    def gerar(self) -> bytes:
        saida = BytesIO()
        documento = SimpleDocTemplate(
            saida,
            pagesize=self._tamanho(),
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=32 * mm,
            bottomMargin=16 * mm,
            title=self.titulo,
            author=self.autor or "contratos-spi",
        )
        cabecalho: list[Flowable] = [Paragraph(escape(self.titulo), ESTILO_TITULO)]
        if self.subtitulo:
            cabecalho.append(texto(self.subtitulo, ESTILO_SUBTITULO))
        documento.build(cabecalho + self.blocos, onFirstPage=self._desenhar_moldura, onLaterPages=self._desenhar_moldura)
        return saida.getvalue()


def mesclar_pdfs(partes: Iterable[bytes | Path]) -> bytes:
    """Junta vários PDFs, na ordem recebida, em um único arquivo (documentos consolidados)."""
    escritor = PdfWriter()
    for parte in partes:
        leitor = PdfReader(BytesIO(parte) if isinstance(parte, bytes) else str(parte))
        for pagina in leitor.pages:
            escritor.add_page(pagina)
    saida = BytesIO()
    escritor.write(saida)
    return saida.getvalue()
