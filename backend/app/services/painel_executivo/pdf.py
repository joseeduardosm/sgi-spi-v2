# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar o PDF de cada slide do Painel Executivo (números, tabelas e gráficos desenhados com o reportlab).
"""PDF de um slide, em paisagem A4. Os gráficos são desenhados a partir dos mesmos dados do slide."""

from decimal import Decimal
from io import BytesIO

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.painel_executivo import SlideContratos, SlideRh, SlideTarefas

VERMELHO = colors.HexColor("#c82331")
CINZA = colors.HexColor("#586372")
AZUL = colors.HexColor("#2f5d8a")
VERDE = colors.HexColor("#2f9e6b")
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
estilos = getSampleStyleSheet()
TITULO = ParagraphStyle("t", parent=estilos["Title"], textColor=VERMELHO, alignment=0, fontSize=20)
SUBTITULO = ParagraphStyle("s", parent=estilos["Heading3"], textColor=CINZA, fontSize=11)
TEXTO = ParagraphStyle("x", parent=estilos["BodyText"], fontSize=9)


def _brl(valor: Decimal | float) -> str:
    """R$ 1.234,56 (formato brasileiro)."""
    return "R$ " + f"{Decimal(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _mi(valor: Decimal | float) -> float:
    """Valor em milhares de reais, para caber no eixo do gráfico."""
    return float(valor) / 1000


def _cartoes(itens: list[tuple[str, str]]) -> Table:
    """Linha de indicadores: número grande e legenda embaixo."""
    numeros = [Paragraph(f'<font size="18" color="#c82331"><b>{v}</b></font><br/><font size="8" color="#586372">{r}</font>', TEXTO) for r, v in itens]
    tabela = Table([numeros], colWidths=[24 * cm / len(itens)] * len(itens))
    tabela.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return tabela


def _tabela(cabecalho: list[str], linhas: list[list[str]], larguras: list[float] | None = None) -> Table:
    dados = [cabecalho, *(linhas or [["—"] + [""] * (len(cabecalho) - 1)])]
    tabela = Table(dados, colWidths=larguras, repeatRows=1)
    tabela.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), VERMELHO), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8),
                                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7f8")])]))
    return tabela


def _barras(rotulos: list[str], series: list[tuple[str, list[float], colors.Color]], largura=24 * cm, altura=6.5 * cm) -> Drawing:
    desenho = Drawing(largura, altura)
    grafico = VerticalBarChart()
    grafico.x, grafico.y, grafico.width, grafico.height = 40, 30, largura - 60, altura - 50
    grafico.data = [s[1] for s in series]
    grafico.categoryAxis.categoryNames = rotulos
    grafico.categoryAxis.labels.fontSize = 7
    grafico.valueAxis.labels.fontSize = 7
    grafico.valueAxis.valueMin = 0
    for i, (_, _, cor) in enumerate(series):
        grafico.bars[i].fillColor = cor
    legenda = Legend()
    legenda.x, legenda.y, legenda.fontSize, legenda.alignment = largura - 200, altura - 5, 8, "right"
    legenda.colorNamePairs = [(cor, nome) for nome, _, cor in series]
    legenda.columnMaximum = 1
    desenho.add(grafico)
    desenho.add(legenda)
    return desenho


def _linhas(series: list[tuple[str, list[float], colors.Color]], largura=24 * cm, altura=6.5 * cm) -> Drawing:
    desenho = Drawing(largura, altura)
    grafico = LinePlot()
    grafico.x, grafico.y, grafico.width, grafico.height = 40, 30, largura - 60, altura - 50
    grafico.data = [[(i + 1, v) for i, v in enumerate(s[1])] for s in series]
    for i, (_, _, cor) in enumerate(series):
        grafico.lines[i].strokeColor = cor
        grafico.lines[i].strokeWidth = 2
    grafico.xValueAxis.valueMin, grafico.xValueAxis.valueMax, grafico.xValueAxis.valueSteps = 1, 12, list(range(1, 13))
    grafico.xValueAxis.labelTextFormat = lambda v: MESES[int(v) - 1]
    grafico.xValueAxis.labels.fontSize = grafico.yValueAxis.labels.fontSize = 7
    legenda = Legend()
    legenda.x, legenda.y, legenda.fontSize, legenda.alignment = largura - 200, altura - 5, 8, "right"
    legenda.colorNamePairs = [(cor, nome) for nome, _, cor in series]
    legenda.columnMaximum = 1
    desenho.add(grafico)
    desenho.add(legenda)
    return desenho


def _documento(titulo: str, subtitulo: str, partes: list) -> bytes:
    saida = BytesIO()
    doc = SimpleDocTemplate(saida, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.3 * cm, bottomMargin=1.2 * cm,
                            title=f"Painel Executivo - {titulo}", author="SGI SPI")
    doc.build([Paragraph(f"Painel Executivo · {titulo}", TITULO), Paragraph(subtitulo, SUBTITULO), Spacer(1, 6), *partes])
    return saida.getvalue()


def contratos(s: SlideContratos) -> bytes:
    e = s.execucao
    partes = [
        _cartoes([("Contratos ativos", str(s.numeros.contratos_ativos)), ("A vencer (90 dias)", str(s.numeros.contratos_a_vencer)),
                  ("Valor global dos ativos", _brl(s.numeros.valor_global_ativos)), (f"Pago em {s.exercicio}", _brl(e.total_pago)),
                  ("Saldo de empenho", _brl(e.saldo_empenho))]),
        Spacer(1, 8), Paragraph(f"Execução em {s.exercicio} (R$ mil): previsto × medido × pago", SUBTITULO),
        _barras(MESES, [("Previsto", [_mi(m.previsto) for m in e.meses], colors.lightgrey), ("Medido", [_mi(m.medido) for m in e.meses], AZUL),
                        ("Pago", [_mi(m.pago) for m in e.meses], VERMELHO)]),
        Paragraph("Vencimentos e riscos", SUBTITULO),
        Paragraph(" · ".join(f"vencem em até {v.ate_dias} dias: <b>{v.contratos}</b>" for v in s.vencimentos)
                  + f" · contratos com risco alto: <b>{s.alertas_altos}</b> · risco médio: <b>{s.alertas_medios}</b>", TEXTO),
        Spacer(1, 4),
        _tabela(["Contrato", "Empresa", "Gravidade", "Riscos", "Principal risco"],
                [[f"{r.contrato_numero} {r.contrato_apelido}".strip(), r.empresa[:38], r.gravidade, str(r.riscos), r.principal[:80]] for r in s.maiores_riscos]),
    ]
    return _documento("Contratos", f"Exercício {s.exercicio} · gerado em {s.gerado_em:%d/%m/%Y %H:%M}", partes)


def rh(s: SlideRh) -> bytes:
    partes = [
        _cartoes([("Afastados hoje", str(len(s.afastados_hoje))), ("Férias a vencer (90 dias)", str(len(s.ferias_a_vencer))),
                  ("Setores em alerta", str(len(s.alertas_setor)))]),
        Spacer(1, 8), Paragraph(f"Pessoas afastadas por mês em {s.ano}", SUBTITULO),
        _barras(MESES, [("Férias", [float(m.ferias) for m in s.por_mes], VERDE), ("Licença-prêmio", [float(m.licenca_premio) for m in s.por_mes], AZUL)]),
        Paragraph("De férias ou licença hoje", SUBTITULO),
        _tabela(["Nome", "Setor", "Tipo", "Até"], [[a.nome, a.setor, "Férias" if a.tipo == "ferias" else "Licença-prêmio", f"{a.fim:%d/%m/%Y}"] for a in s.afastados_hoje[:12]]),
        Spacer(1, 6), Paragraph("Férias a vencer", SUBTITULO),
        _tabela(["Nome", "Setor", "Dias disponíveis", "Período termina em"], [[f.nome, f.setor, str(f.disponivel), f"{f.periodo_fim:%d/%m/%Y}"] for f in s.ferias_a_vencer]),
    ]
    return _documento("RH", f"Ano {s.ano} · gerado em {s.gerado_em:%d/%m/%Y %H:%M}", partes)


def tarefas(s: SlideTarefas) -> bytes:
    partes = [
        _cartoes([("Abertas", str(s.abertas)), ("Atrasadas", str(s.atrasadas)), ("Vencem hoje", str(s.vencem_hoje)), ("Críticas", str(s.criticas)),
                  ("Em validação", str(s.em_validacao)), ("Concluídas em 30 dias", str(s.concluidas_30_dias))]),
        Spacer(1, 8), Paragraph("Criadas × concluídas por semana (últimas 12)", SUBTITULO),
        _barras([f"{x.inicio:%d/%m}" for x in s.semanas], [("Criadas", [float(x.criadas) for x in s.semanas], colors.lightgrey),
                                                          ("Concluídas", [float(x.concluidas) for x in s.semanas], VERMELHO)]),
        Paragraph("Equipes", SUBTITULO),
        _tabela(["Equipe", "Abertas", "Atrasadas", "Críticas", "Carga", "Faixa"], [[e.equipe, str(e.abertas), str(e.atrasadas), str(e.criticas), f"{e.carga:g}", e.faixa] for e in s.equipes]),
    ]
    return _documento("Tarefas", f"gerado em {s.gerado_em:%d/%m/%Y %H:%M}", partes)
