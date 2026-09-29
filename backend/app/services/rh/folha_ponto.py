# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar a folha de ponto (registro de frequência) mensal do servidor em PDF.
"""Folha de ponto em PDF, no modelo de frequência da SPI (A4 retrato, duas páginas).

1ª página:
- cabeçalho com o brasão, "Governo do Estado de São Paulo / Secretaria de Parcerias em Investimentos", o **setor** do
  servidor (Departamento) e "REGISTRO DE PONTO – MÊS/ANO";
- identificação: servidor, RG/CIN, RS/PV, função e, dos dados funcionais da CGP, jornada, plantão, horário de trabalho,
  horário de estudante e intervalo (o que faltar sai em branco);
- uma linha por dia: Entrada e Saída (hora e assinatura), Observações e Visto do Superior Imediato. Sábados e domingos,
  feriados e pontos facultativos cadastrados e férias ou licença-prêmio **aprovadas ou gozadas** vêm marcados, nesta
  prioridade (um feriado dentro das férias continua como feriado).

2ª página: "Informações financeiras" em branco (férias, média de GTN, ACA, GTN, serviço extraordinário, substituição
eventual, vale-transporte), assinaturas e o quadro de consolidação.
"""

import calendar
from datetime import date, time
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rh import Afastamento, DadosFuncionais
from app.models.usuario import Usuario
from app.services.documentos.pdf import ESTILO_TEXTO, TEXTO
from app.services.modelo_email import ARQUIVO_BRASAO
from app.services.rh import servico_feriados

MESES = ("JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO")
FIM_DE_SEMANA = {5: "SÁBADO", 6: "DOMINGO"}
MARCAS_AFASTAMENTO = {"ferias": "FÉRIAS", "licenca_premio": "LICENÇA-PRÊMIO"}
TRACO = "---------"
CINZA = colors.HexColor("#e7e9ec")
LINHA = colors.HexColor("#5b6570")

# Estilos próprios da folha (fonte menor que a dos relatórios, para caber o mês numa página)
ESTILO = ParagraphStyle("folha", parent=ESTILO_TEXTO, fontSize=8, leading=10)
ESTILO_NEGRITO = ParagraphStyle("folha_negrito", parent=ESTILO, fontName="Helvetica-Bold")
ESTILO_CENTRO = ParagraphStyle("folha_centro", parent=ESTILO, alignment=TA_CENTER)
ESTILO_CENTRO_NEGRITO = ParagraphStyle("folha_centro_negrito", parent=ESTILO_CENTRO, fontName="Helvetica-Bold")
ESTILO_GOVERNO = ParagraphStyle("folha_governo", parent=ESTILO_NEGRITO, fontSize=11, leading=14, textColor=TEXTO)
ESTILO_SETOR = ParagraphStyle("folha_setor", parent=ESTILO_CENTRO_NEGRITO, fontSize=11, leading=14)
ESTILO_TITULO = ParagraphStyle("folha_titulo", parent=ESTILO_CENTRO_NEGRITO, fontSize=12, leading=15)
ESTILO_OBSERVACAO = ParagraphStyle("folha_observacao", parent=ESTILO, fontSize=7, leading=8.5)


def rotulo_competencia(ano: int, mes: int) -> str:
    """Ex.: "OUTUBRO/2026"."""
    return f"{MESES[mes - 1]}/{ano}"


def _hora(valor: time | None) -> str:
    return f"{valor.hour}:{valor.minute:02d}" if valor else ""


def _faixa(inicio: time | None, fim: time | None) -> str:
    """Ex.: "das 9:00 às 18:00" (vazio quando não informado)."""
    return f"das {_hora(inicio)} às {_hora(fim)}" if inicio and fim else ""


def _sim_nao(valor: bool | None, informado: bool) -> str:
    return ("Sim" if valor else "Não") if informado else ""


def marcacoes(sessao: Session, usuario_id: int, ano: int, mes: int) -> dict[int, tuple[str, str]]:
    """Por dia do mês: (marca das colunas de Entrada e Saída, texto de Observações). Dias úteis sem marca ficam de fora."""
    ultimo = calendar.monthrange(ano, mes)[1]
    inicio, fim = date(ano, mes, 1), date(ano, mes, ultimo)
    feriados = servico_feriados.no_intervalo(sessao, inicio, fim)
    afastamentos = list(sessao.scalars(select(Afastamento).where(
        Afastamento.usuario_id == usuario_id, Afastamento.status.in_(("aprovado", "gozado")),
        Afastamento.inicio <= fim, Afastamento.fim >= inicio,
    )))
    resultado: dict[int, tuple[str, str]] = {}
    for dia in range(1, ultimo + 1):
        data = date(ano, mes, dia)
        if data.weekday() in FIM_DE_SEMANA:
            resultado[dia] = (FIM_DE_SEMANA[data.weekday()], "")
        elif data in feriados:
            f = feriados[data]
            resultado[dia] = ("FERIADO" if f.tipo == "feriado" else "PONTO FACULTATIVO", f.descricao)
        else:
            afastamento = next((a for a in afastamentos if a.inicio <= data <= a.fim), None)
            if afastamento is not None:
                periodo = f"{afastamento.inicio:%d/%m/%Y} a {afastamento.fim:%d/%m/%Y}"
                resultado[dia] = (MARCAS_AFASTAMENTO[afastamento.tipo], periodo if data == max(afastamento.inicio, inicio) else "")
    return resultado


def _p(texto: str, estilo: ParagraphStyle = ESTILO) -> Paragraph:
    return Paragraph(escape(texto), estilo)


def _campo(rotulo: str, valor: str) -> Paragraph:
    """"Rótulo: valor", com o rótulo em negrito."""
    return Paragraph(f"<b>{escape(rotulo)}</b> {escape(valor)}", ESTILO)


def _cabecalho(setor: str, ano: int, mes: int, largura: float) -> list:
    # Só o brasão (a mesma imagem do cabeçalho dos e-mails), sem texto embutido
    brasao = Image(str(ARQUIVO_BRASAO), width=14 * mm, height=16 * mm) if ARQUIVO_BRASAO.exists() else _p("")
    governo = [_p("GOVERNO DO ESTADO DE SÃO PAULO", ESTILO_GOVERNO), _p("SECRETARIA DE PARCERIAS EM INVESTIMENTOS", ESTILO_GOVERNO)]
    topo = Table([[brasao, governo]], colWidths=[20 * mm, largura - 20 * mm])
    topo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return [topo, Spacer(1, 2 * mm), _p(setor or " ", ESTILO_SETOR), Spacer(1, 1 * mm),
            _p(f"REGISTRO DE PONTO – {rotulo_competencia(ano, mes)}", ESTILO_TITULO), Spacer(1, 3 * mm)]


def _identificacao(usuario: Usuario, f: DadosFuncionais | None, largura: float) -> Table:
    jornada = f"{f.jornada_semanal_horas} horas/semanais" if f and f.jornada_semanal_horas else ""
    linhas = [
        [_campo("Servidor:", (usuario.nome_completo or usuario.login).upper()), ""],
        [_campo("RG/CIN nº:", (f.rg_cin if f else None) or ""), _campo("RS/PV nº:", (f.rs_pv if f else None) or "")],
        [_campo("Função:", usuario.cargo or ""), ""],
        [_campo("Jornada de Trabalho:", jornada), _campo("Regime de Plantão:", _sim_nao(f and f.regime_plantao, f is not None))],
        [_campo("Horário de Trabalho:", _faixa(f and f.horario_trabalho_inicio, f and f.horario_trabalho_fim)),
         _campo("Horário de Estudante:", _sim_nao(f and f.horario_estudante, f is not None))],
        [_campo("Intervalo de Almoço e Descanso:", _faixa(f and f.intervalo_inicio, f and f.intervalo_fim)), ""],
    ]
    tabela = Table(linhas, colWidths=[largura * 0.6, largura * 0.4])
    tabela.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINHA),
        ("SPAN", (0, 0), (1, 0)), ("SPAN", (0, 2), (1, 2)), ("SPAN", (0, 5), (1, 5)),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
    ]))
    return tabela


def _grade(ano: int, mes: int, marcas: dict[int, tuple[str, str]], largura: float) -> Table:
    colunas = [9 * mm, 15 * mm, 33 * mm, 15 * mm, 33 * mm]
    colunas += [(largura - sum(colunas)) * 0.55, (largura - sum(colunas)) * 0.45]
    linhas = [
        [_p("Dia", ESTILO_CENTRO_NEGRITO), _p("Entrada", ESTILO_CENTRO_NEGRITO), "", _p("Saída", ESTILO_CENTRO_NEGRITO), "",
         _p("Observações", ESTILO_CENTRO_NEGRITO), _p("Visto do Superior Imediato", ESTILO_CENTRO_NEGRITO)],
        ["", _p("Hora", ESTILO_CENTRO_NEGRITO), _p("Assinatura", ESTILO_CENTRO_NEGRITO), _p("Hora", ESTILO_CENTRO_NEGRITO),
         _p("Assinatura", ESTILO_CENTRO_NEGRITO), "", ""],
    ]
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.5, LINHA),
        ("SPAN", (1, 0), (2, 0)), ("SPAN", (3, 0), (4, 0)), ("SPAN", (0, 0), (0, 1)), ("SPAN", (5, 0), (5, 1)), ("SPAN", (6, 0), (6, 1)),
        ("BACKGROUND", (0, 0), (-1, 1), CINZA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
        linha = len(linhas)
        marca, observacao = marcas.get(dia, ("", ""))
        if marca:
            texto = f"{TRACO} {marca}"
            linhas.append([_p(str(dia), ESTILO_CENTRO), _p(texto, ESTILO_CENTRO_NEGRITO), "", _p(texto, ESTILO_CENTRO_NEGRITO), "",
                           _p(observacao, ESTILO_OBSERVACAO), ""])
            estilo += [("SPAN", (1, linha), (2, linha)), ("SPAN", (3, linha), (4, linha)), ("BACKGROUND", (0, linha), (4, linha), CINZA)]
        else:
            linhas.append([_p(str(dia), ESTILO_CENTRO), "", "", "", "", "", ""])
    tabela = Table(linhas, colWidths=colunas, rowHeights=[5.5 * mm, 5 * mm] + [6.1 * mm] * (len(linhas) - 2), repeatRows=2)
    tabela.setStyle(TableStyle(estilo))
    return tabela


def _informacoes_financeiras(largura: float) -> list:
    data = "___/___/_____"
    linhas = [
        [_p("INFORMAÇÕES FINANCEIRAS", ESTILO_CENTRO_NEGRITO), "", ""],
        [_p("FÉRIAS", ESTILO_NEGRITO), _p(f"Período de {data} até {data}"), _p("Quantidade: ________")],
        [_p("MÉDIA de GTN", ESTILO_NEGRITO), _p("Período: ____________________"), _p("")],
        [_p("ACA", ESTILO_NEGRITO), _p("Período: ____________________"), _p("(Entre 8 e 12 / Superior a 12) horas diárias")],
        [_p("GTN", ESTILO_NEGRITO), _p("Período: ____________________"), _p("Percentual GTN: ________")],
        [_p("SERVIÇO EXTRAORDINÁRIO", ESTILO_NEGRITO), _p(f"De {data} até {data}"), _p("Quantidade (20% / 10%): ________")],
        [_p("SUBSTITUIÇÃO EVENTUAL", ESTILO_NEGRITO), _p(f"De {data} até {data}"), _p("Cargo/Função Substituído: ____________")],
        [_p("VALE TRANSPORTE – CLT", ESTILO_NEGRITO), _p(f"De {data} até {data}"), _p("(Sim / Não): ________")],
    ]
    tabela = Table(linhas, colWidths=[largura * 0.26, largura * 0.37, largura * 0.37], rowHeights=[7 * mm] + [10 * mm] * 7)
    tabela.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, LINHA), ("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), CINZA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    # Duas linhas de assinatura separadas por um vão (colunas 0 e 2)
    vao = 16 * mm
    assinaturas = Table(
        [["", "", ""], [_p("Assinatura do Servidor", ESTILO_CENTRO), "", _p("Assinatura do Superior Imediato", ESTILO_CENTRO)],
         [_p(f"Data: {data}"), "", ""]],
        colWidths=[(largura - vao) / 2, vao, (largura - vao) / 2], rowHeights=[16 * mm, 6 * mm, 9 * mm],
    )
    assinaturas.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.6, LINHA), ("LINEBELOW", (2, 0), (2, 0), 0.6, LINHA), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]))
    return [tabela, Spacer(1, 6 * mm), assinaturas]


def _consolidacao(largura: float) -> list:
    linhas = [[_p("CONSOLIDAÇÃO", ESTILO_CENTRO_NEGRITO)]] + [[""] for _ in range(11)]
    quadro = Table(linhas, colWidths=[largura], rowHeights=[7 * mm] + [8 * mm] * 11)
    quadro.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINHA), ("BACKGROUND", (0, 0), (-1, 0), CINZA), ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINHA),
    ]))
    rodape = Table(
        [[_p("Data ___/___/_____"), ""], ["", _p("Assinatura do Superior Imediato ou do Responsável", ESTILO_CENTRO)]],
        colWidths=[largura * 0.4, largura * 0.6], rowHeights=[14 * mm, 6 * mm],
    )
    rodape.setStyle(TableStyle([("LINEBELOW", (1, 0), (1, 0), 0.6, LINHA), ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    return [quadro, Spacer(1, 4 * mm), rodape]


def gerar(sessao: Session, usuario: Usuario, ano: int, mes: int) -> bytes:
    """PDF da folha de ponto do usuário na competência (mês/ano)."""
    margem = 12 * mm
    largura = A4[0] - 2 * margem
    buffer = BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=margem, rightMargin=margem, topMargin=10 * mm, bottomMargin=10 * mm,
                                  title=f"Folha de ponto – {rotulo_competencia(ano, mes)}", author="SGI SPI")
    funcionais = sessao.get(DadosFuncionais, usuario.id)
    conteudo = [
        *_cabecalho(usuario.departamento, ano, mes, largura),
        _identificacao(usuario, funcionais, largura),
        Spacer(1, 3 * mm),
        _grade(ano, mes, marcacoes(sessao, usuario.id, ano, mes), largura),
        PageBreak(),
        # 2ª página: identificação resumida no topo (a folha pode ser impressa em frente e verso)
        _p(f"REGISTRO DE PONTO – {rotulo_competencia(ano, mes)} · {(usuario.nome_completo or usuario.login).upper()}", ESTILO_TITULO),
        Spacer(1, 4 * mm),
        *_informacoes_financeiras(largura),
        Spacer(1, 8 * mm),
        *_consolidacao(largura),
    ]
    documento.build(conteudo)
    return buffer.getvalue()
