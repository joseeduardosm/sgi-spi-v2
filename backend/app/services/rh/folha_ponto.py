# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar a folha de ponto (registro de frequência) mensal do servidor em PDF.
"""Folha de ponto em PDF, fiel ao modelo de frequência da SPI (`apoio/10-2026 - FOLHA DE FREQUENCIA.doc`).

A4 retrato, frente e verso, com a mesma estrutura do modelo:

- **Frente:** cabeçalho em caixa (brasão com "Governo do Estado de São Paulo / Secretaria de Parcerias em
  Investimentos" | governo, secretaria, **setor** do servidor e "REGISTRO DE PONTO MÊS/ANO"); identificação em duas
  colunas (servidor, função, jornada, horários e intervalo | RG/CIN, RS/PV, plantão e estudante); a **tabela do mês
  inteira** (Dia | Entrada: Hora, Assinatura | Saída: Hora, Assinatura | Observações | Visto do Superior Imediato);
  o quadro "Informações financeiras" (em branco) e as assinaturas do servidor e do superior.
- **Verso:** só as anotações: o mesmo cabeçalho, "CONSOLIDAÇÃO" com as linhas pautadas, data e assinatura do superior
  imediato ou do responsável.

**Pré-requisitos** (`verificar`): a folha só é gerada com os dados funcionais preenchidos pela CGP (jornada, horário de
trabalho, intervalo, RG/CIN e RS/PV) e sem alteração de cadastro aguardando validação. Caso contrário, `FolhaBloqueada`,
e a CGP recebe aviso com e-mail (no máximo um por motivo, por usuário e por dia).

Nas linhas da tabela, "---------" na Hora e a marca em vermelho na Assinatura, nesta prioridade: sábado e domingo;
feriado ou ponto facultativo cadastrado (descrição em Observações); férias ou licença-prêmio **aprovadas ou gozadas**
(período em Observações no primeiro dia do mês em que aparecem).
"""

import calendar
from datetime import date, time
from functools import lru_cache
from io import BytesIO
from xml.sax.saxutils import escape

from PIL import Image as ImagemPil
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
from app.services.documentos.pdf import CAMINHO_BRASAO
from app.services import servico_mensagens
from app.services.rh import servico_feriados

MESES = ("JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO")
FIM_DE_SEMANA = {5: "SÁBADO", 6: "DOMINGO"}
MARCAS_AFASTAMENTO = {"ferias": "FÉRIAS", "licenca_premio": "LICENÇA-PRÊMIO"}
TRACO = "---------"
PRETO = colors.black
VERMELHO = colors.HexColor("#c00000")
CINZA_FAIXA = colors.HexColor("#f2f2f2")
# Área útil (A4 com as margens do modelo)
MARGEM_LATERAL = 14 * mm
LARGURA = A4[0] - 2 * MARGEM_LATERAL
LINHAS_CONSOLIDACAO = 42


def _estilo(nome: str, tamanho: float, negrito: bool = False, centro: bool = False, fonte: str = "Helvetica",
            cor=PRETO) -> ParagraphStyle:
    return ParagraphStyle(nome, fontName=f"{fonte}-Bold" if negrito else fonte, fontSize=tamanho, leading=tamanho * 1.18,
                          alignment=TA_CENTER if centro else 0, textColor=cor)


# Tipografia do modelo: Arial → Helvetica; os textos pequenos do quadro financeiro em Times, como no .doc
CAB = _estilo("cab", 8.5, negrito=True, centro=True)
ROTULO_ID = _estilo("rotulo_id", 9.5)
TITULO_TABELA = _estilo("titulo_tabela", 8, negrito=True, centro=True)
DIA = _estilo("dia", 8, negrito=True, centro=True)
MARCA = _estilo("marca", 9, negrito=True, centro=True, cor=VERMELHO)
TRACO_ESTILO = _estilo("traco", 7, centro=True)
OBSERVACAO = _estilo("observacao", 5.8, negrito=True, centro=True)
FIN_ROTULO = _estilo("fin_rotulo", 7.5, negrito=True, centro=True)
FIN_TEXTO = _estilo("fin_texto", 6.2, negrito=True, centro=True, fonte="Times")
ASSINATURA = _estilo("assinatura", 7.5, negrito=True, centro=True)
CONSOLIDACAO = _estilo("consolidacao", 10, negrito=True, centro=True)
RODAPE_VERSO = _estilo("rodape_verso", 8.5, negrito=True, fonte="Times")
RODAPE_VERSO_CENTRO = _estilo("rodape_verso_centro", 8.5, negrito=True, centro=True, fonte="Times")


# Dados funcionais sem os quais a folha não sai (os de plantão e estudante já nascem como "Não")
CAMPOS_OBRIGATORIOS = {
    "jornada_semanal_horas": "Jornada de trabalho",
    "horario_trabalho_inicio": "Horário de trabalho",
    "intervalo_inicio": "Intervalo de almoço e descanso",
    "rg_cin": "RG/CIN nº",
    "rs_pv": "RS/PV nº",
}
PREFIXO_AVISO_DADOS = "folha-ponto:dados:"
PREFIXO_AVISO_VALIDACAO = "folha-ponto:validacao:"


class FolhaBloqueada(Exception):
    """A folha não pode ser gerada ainda (vira 409 com o código do motivo)."""

    def __init__(self, detalhe: str, codigo: str) -> None:
        super().__init__(detalhe)
        self.codigo = codigo


def campos_faltantes(funcionais: DadosFuncionais | None) -> list[str]:
    """Rótulos dos dados funcionais obrigatórios ainda não preenchidos."""
    return [rotulo for campo, rotulo in CAMPOS_OBRIGATORIOS.items() if not (funcionais and getattr(funcionais, campo))]


def verificar(sessao: Session, usuario: Usuario, hoje: date) -> None:
    """Confere os pré-requisitos; se faltar algo, avisa a CGP (com e-mail) e lança `FolhaBloqueada`."""
    from app.services.rh.papeis import usuarios_cgp
    from app.services.rh.servico_cadastro import ROTULOS, pendentes_do_usuario

    nome = usuario.nome_completo or usuario.login
    link = f"/rh/validacoes?usuario={usuario.id}"
    cgp = [u.id for u in usuarios_cgp(sessao)]
    pendentes = pendentes_do_usuario(sessao, usuario.id)
    if pendentes:
        campos = ", ".join(dict.fromkeys(ROTULOS.get(a.campo, a.campo) for a in pendentes))
        servico_mensagens.notificar(
            sessao, cgp, f"{nome} quer baixar a folha de ponto, mas tem alterações de cadastro aguardando validação",
            f"{nome} tentou gerar a folha de ponto, mas tem alterações de cadastro aguardando validação da CGP: {campos}.\n\n"
            "A folha fica disponível assim que as alterações forem validadas ou recusadas.",
            chave=f"{PREFIXO_AVISO_VALIDACAO}{usuario.id}:{hoje:%Y%m%d}", categoria="pendencia", link=link, email=True,
        )
        sessao.commit()
        raise FolhaBloqueada(
            f"Você tem alterações de cadastro aguardando validação da CGP ({campos}). A folha de ponto fica disponível "
            "depois que a CGP analisar essas alterações. A CGP já foi avisada por e-mail.", "folha_cadastro_pendente",
        )
    faltantes = campos_faltantes(sessao.get(DadosFuncionais, usuario.id))
    if faltantes:
        lista = ", ".join(faltantes)
        servico_mensagens.notificar(
            sessao, cgp, f"{nome} quer baixar a folha de ponto, mas ainda não tem os dados preenchidos",
            f"{nome} tentou gerar a folha de ponto, mas os dados funcionais dele(a) ainda não foram preenchidos pela CGP: {lista}.\n\n"
            "Preencha em Usuários (janela de edição) ou em RH › Validações, bloco \"Jornada e documentos\".",
            chave=f"{PREFIXO_AVISO_DADOS}{usuario.id}:{hoje:%Y%m%d}", categoria="pendencia", link=link, email=True,
        )
        sessao.commit()
        raise FolhaBloqueada(
            f"Seus dados funcionais ainda não foram preenchidos pela CGP ({lista}). A folha de ponto fica disponível "
            "depois do preenchimento. A CGP já foi avisada por e-mail.", "folha_dados_incompletos",
        )


def encerrar_aviso_dados(sessao: Session, funcionais: DadosFuncionais) -> None:
    """Com os dados completos, os avisos "dados não preenchidos" deste usuário deixam de pedir ação da CGP."""
    if not campos_faltantes(funcionais):
        servico_mensagens.encerrar(sessao, prefixo=f"{PREFIXO_AVISO_DADOS}{funcionais.usuario_id}:")


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


def _p(texto: str, estilo: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(texto), estilo)


@lru_cache(maxsize=1)
def _brasao_recortado() -> tuple[bytes, int, int] | None:
    """Brasão com "Governo do Estado de São Paulo / Secretaria de Parcerias em Investimentos", sem a margem branca da
    imagem original (o bloco da célula esquerda do cabeçalho do modelo)."""
    if not CAMINHO_BRASAO.exists():
        return None
    imagem = ImagemPil.open(CAMINHO_BRASAO).convert("RGBA")
    fundo = ImagemPil.new("RGBA", imagem.size, "white")
    caixa = ImagemPil.alpha_composite(fundo, imagem).convert("L").point(lambda v: 0 if v > 245 else 255).getbbox()
    recorte = imagem.crop(caixa) if caixa else imagem
    saida = BytesIO()
    recorte.save(saida, format="PNG")
    return saida.getvalue(), recorte.width, recorte.height


def _cabecalho(setor: str, ano: int, mes: int) -> Table:
    """Caixa do cabeçalho (frente e verso): brasão | governo, secretaria, setor e "REGISTRO DE PONTO MÊS/ANO"."""
    recorte = _brasao_recortado()
    if recorte is not None:
        conteudo, largura_img, altura_img = recorte
        altura = 19 * mm
        brasao = Image(BytesIO(conteudo), width=altura * largura_img / altura_img, height=altura)
    else:
        brasao = _p("", CAB)
    textos = [_p("GOVERNO DO ESTADO DE SÃO PAULO", CAB), _p("SECRETARIA DE PARCERIAS EM INVESTIMENTOS", CAB),
              _p(setor or " ", CAB), _p(f"REGISTRO DE PONTO {rotulo_competencia(ano, mes)}", CAB)]
    caixa = Table([[brasao, textos]], colWidths=[42 * mm, LARGURA - 42 * mm], rowHeights=[24 * mm])
    caixa.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, PRETO), ("LINEAFTER", (0, 0), (0, 0), 0.6, PRETO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (0, 0), "CENTER"),
    ]))
    return caixa


def _campo(rotulo: str, valor: str, valor_negrito: bool = False) -> Paragraph:
    """"Rótulo: valor", com o rótulo em negrito (e o valor menor), como no modelo."""
    valor_html = f"<b>{escape(valor)}</b>" if valor_negrito else f'<font size="7.5">{escape(valor)}</font>'
    return Paragraph(f"<b>{escape(rotulo)}</b> {valor_html}", ROTULO_ID)


def _identificacao(usuario: Usuario, f: DadosFuncionais | None) -> Table:
    jornada = f"{f.jornada_semanal_horas} horas/semanais" if f and f.jornada_semanal_horas else ""
    esquerda = [
        _campo("Servidor:", (usuario.nome_completo or usuario.login).upper(), valor_negrito=True),
        _campo("Função:", usuario.cargo or ""),
        _campo("Jornada de Trabalho:", jornada),
        _campo("Horário de Trabalho:", _faixa(f and f.horario_trabalho_inicio, f and f.horario_trabalho_fim)),
        _campo("Intervalo de Almoço e Descanso:", _faixa(f and f.intervalo_inicio, f and f.intervalo_fim)),
    ]
    direita = [
        _campo("RG/CIN nº:", (f.rg_cin if f else None) or ""),
        _campo("RS/PV nº:", (f.rs_pv if f else None) or ""),
        _campo("Regime de Plantão:", _sim_nao(f and f.regime_plantao, f is not None)),
        _campo("Horário de Estudante:", _sim_nao(f and f.horario_estudante, f is not None)),
        _p("", ROTULO_ID),
    ]
    tabela = Table([[e, d] for e, d in zip(esquerda, direita)], colWidths=[LARGURA * 0.62, LARGURA * 0.38])
    tabela.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tabela


def _grade(ano: int, mes: int, marcas: dict[int, tuple[str, str]]) -> Table:
    """Tabela do mês inteiro, com as larguras de coluna do modelo."""
    colunas = [10 * mm, 13 * mm, 46 * mm, 13 * mm, 45 * mm, 37 * mm]
    colunas.append(LARGURA - sum(colunas))
    linhas = [
        [_p("Dia", TITULO_TABELA), _p("Entrada", TITULO_TABELA), "", _p("Saída", TITULO_TABELA), "",
         _p("Observações", TITULO_TABELA), _p("Visto do Superior Imediato", TITULO_TABELA)],
        ["", _p("Hora", TITULO_TABELA), _p("Assinatura", TITULO_TABELA), _p("Hora", TITULO_TABELA), _p("Assinatura", TITULO_TABELA), "", ""],
    ]
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
        marca, observacao = marcas.get(dia, ("", ""))
        if marca:
            rotulo = _p(marca, MARCA)
            linhas.append([_p(str(dia), DIA), _p(TRACO, TRACO_ESTILO), rotulo, _p(TRACO, TRACO_ESTILO), rotulo,
                           _p(observacao, OBSERVACAO), ""])
        else:
            linhas.append([_p(str(dia), DIA), "", "", "", "", "", ""])
    tabela = Table(linhas, colWidths=colunas, rowHeights=[5 * mm, 5 * mm] + [5.35 * mm] * (len(linhas) - 2))
    tabela.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PRETO),
        ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (2, 0)), ("SPAN", (3, 0), (4, 0)), ("SPAN", (5, 0), (5, 1)), ("SPAN", (6, 0), (6, 1)),
        # Como no modelo: cabeçalho centrado; dias e marcas rentes à linha de baixo
        ("VALIGN", (0, 0), (-1, 1), "MIDDLE"), ("VALIGN", (0, 2), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.3),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return tabela


def _informacoes_financeiras() -> Table:
    """Quadro "Informações financeiras" (em branco), com a disposição das células do modelo."""
    # Espaços não separáveis: as barras ficam afastadas para preencher à mão, como no modelo
    esp = "\u00a0" * 6
    data = f"{esp}/{esp}/{esp}"
    colunas = [24 * mm, 43 * mm, 26 * mm, 27 * mm, 44 * mm]
    colunas.append(LARGURA - sum(colunas))
    r, t = FIN_ROTULO, FIN_TEXTO
    linhas = [
        [_p("INFORMAÇÕES FINANCEIRAS", r), "", "", "", "", ""],
        [_p("FÉRIAS", r), Paragraph("<b>Período:</b>", _estilo("fin_esq", 6.2, negrito=True, fonte="Times")), _p("MÉDIA de GTN", r), _p("ACA", r),
         [_p(f"Período de   {data}   Até   {data}", t), _p("(Entre 8 e 12  / Superior a 12 ) horas diárias", t)], _p("Quantidade", t)],
        [_p("GTN", r), [_p("Período", t), _p(f"De   {data}   Até   {data}", t)], [_p("Percentual GTN", t), _p("(20% / 10%)", t)],
         [_p("SERVIÇO", r), _p("EXTRAORDINÁRIO", r)], [_p("Período", t), _p(f"De   {data}   Até   {data}", t)], _p("Quantidade", t)],
        [_p("SUBSTITUIÇÃO EVENTUAL", r), [_p("Período", t), _p("De" + "\u00a0" * 20 + "Até", t)], _p("Cargo/Função Substituído", t), "",
         [_p("VALE TRANSPORTE -", r), _p("CLT (Sim /Não) :", r)], ""],
    ]
    tabela = Table(linhas, colWidths=colunas, rowHeights=[4.2 * mm, 7.5 * mm, 7.5 * mm, 7.5 * mm])
    tabela.setStyle(TableStyle([
        ("GRID", (0, 1), (-1, -1), 0.5, PRETO), ("BOX", (0, 0), (-1, -1), 0.5, PRETO),
        ("SPAN", (0, 0), (-1, 0)),
        ("SPAN", (2, 3), (3, 3)), ("SPAN", (4, 3), (5, 3)),
        ("BACKGROUND", (0, 1), (0, -1), CINZA_FAIXA), ("BACKGROUND", (2, 1), (3, 1), CINZA_FAIXA),
        ("BACKGROUND", (3, 2), (3, 2), CINZA_FAIXA), ("BACKGROUND", (4, 3), (5, 3), CINZA_FAIXA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return tabela


def _assinaturas() -> Table:
    """Faixa cinza com as assinaturas do servidor e do superior imediato e a data."""
    vao = 8 * mm
    colunas = [66 * mm, vao, 66 * mm]
    colunas.append(LARGURA - sum(colunas))
    tabela = Table(
        [["", "", "", ""], [_p("Assinatura do Servidor", ASSINATURA), "", _p("Assinatura do Superior Imediato", ASSINATURA),
                            _p("Data:" + "\u00a0" * 8 + "/" + "\u00a0" * 8 + "/", ASSINATURA)]],
        colWidths=colunas, rowHeights=[11 * mm, 5 * mm],
    )
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CINZA_FAIXA),
        ("LINEBELOW", (0, 0), (0, 0), 0.6, PRETO), ("LINEBELOW", (2, 0), (2, 0), 0.6, PRETO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))
    return tabela


def _verso(setor: str, ano: int, mes: int) -> list:
    """Verso: cabeçalho, "CONSOLIDAÇÃO" com as linhas pautadas, data e assinatura do superior ou do responsável."""
    pautas = Table([[""] for _ in range(LINHAS_CONSOLIDACAO)], colWidths=[LARGURA], rowHeights=[4.6 * mm] * LINHAS_CONSOLIDACAO)
    pautas.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.6, PRETO)]))
    rodape = Table(
        [[_p("Data          ______/______/_______", RODAPE_VERSO), "", _p("_" * 52, RODAPE_VERSO_CENTRO)],
         ["", "", _p("Assinatura do Superior Imediato ou do Responsável", RODAPE_VERSO_CENTRO)]],
        colWidths=[LARGURA * 0.42, LARGURA * 0.05, LARGURA * 0.53],
    )
    rodape.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return [_cabecalho(setor, ano, mes), Spacer(1, 10 * mm), _p("CONSOLIDAÇÃO", CONSOLIDACAO), Spacer(1, 6 * mm), pautas,
            Spacer(1, 14 * mm), rodape]


def gerar(sessao: Session, usuario: Usuario, ano: int, mes: int) -> bytes:
    """PDF da folha de ponto do usuário na competência (mês/ano): frente com a tabela do mês e verso com a consolidação."""
    buffer = BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGEM_LATERAL, rightMargin=MARGEM_LATERAL, topMargin=11 * mm,
                                  bottomMargin=8 * mm, title=f"Folha de ponto – {rotulo_competencia(ano, mes)}", author="SGI SPI")
    funcionais = sessao.get(DadosFuncionais, usuario.id)
    setor = usuario.departamento
    documento.build([
        _cabecalho(setor, ano, mes),
        Spacer(1, 2.5 * mm),
        _identificacao(usuario, funcionais),
        Spacer(1, 1 * mm),
        _grade(ano, mes, marcacoes(sessao, usuario.id, ano, mes)),
        _informacoes_financeiras(),
        _assinaturas(),
        PageBreak(),
        *_verso(setor, ano, mes),
    ])
    return buffer.getvalue()
