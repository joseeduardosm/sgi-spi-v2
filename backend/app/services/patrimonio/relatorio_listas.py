# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar o relatório (PDF consolidado e Excel) das listas de inservíveis, extraviados e das baixas, com fotos e anexos.
"""Relatório das listas de classificação (inservíveis e extraviados) e das baixas.

PDF no formato **consolidado**, como os documentos de Contratos: índice clicável na primeira página, o relatório (item, chapa, descrição com marca e
modelo, local, últimas fotos com data, hora e quem registrou, justificativa e a coluna do anexo), as páginas das fotos em tamanho grande e, por fim,
o anexo de cada item (boletim de ocorrência, e-mail ou foto), cada um precedido de uma contracapa. A coluna do anexo e a das fotos são hiperlinks para
essas páginas. Todas as páginas são numeradas em sequência ("Página X de N").

Excel: as mesmas colunas, com a miniatura da última foto na célula, a aba **Fotos** (fotos grandes, com data, hora e quem registrou) e o nome do anexo.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ImagemExcel
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink
from PIL import Image as ImagemPil, ImageOps
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patrimonio import Baixa, Bem, Classificacao, ItemClassificacao
from app.models.usuario import Usuario
from app.services import servico_anexos
from app.services.documentos.pdf import (
    BORDA, ESTILO_LINK_INDICE, ESTILO_PEQUENO, FUSO_SAO_PAULO, VERMELHO, VERMELHO_SUAVE, DocumentoPdf, EntradaIndice, AlvoLink, contar_paginas,
    contracapa, indice_consolidado, montar_consolidado, texto,
)
from app.services.patrimonio.base import ErroPatrimonio, nome_do_autor
from app.services.patrimonio.servico_baixas import MOTIVOS
from app.services.patrimonio.servico_localizacoes import rotulo_curto

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAXIMO_FOTOS = 3
STATUS = {"rascunho": "Rascunho", "pendente": "Aguardando aprovação", "aprovada": "Aprovada", "parcial": "Aprovada em parte", "recusada": "Recusada"}


def _local(valor: datetime) -> datetime:
    """Horário de Brasília (o PostgreSQL devolve data com fuso; sem fuso, o valor está em UTC)."""
    return (valor if valor.tzinfo else valor.replace(tzinfo=UTC)).astimezone(FUSO_SAO_PAULO)


@dataclass
class Arquivo:
    """Arquivo guardado (foto ou anexo) com quando e por quem foi registrado."""

    nome: str
    caminho: Path
    tipo: str
    quando: datetime | None
    quem: str

    def legenda(self) -> str:
        data = _local(self.quando).strftime("%d/%m/%Y %H:%M") if self.quando else "—"
        return f"{data} · {self.quem or '—'}"

    def existe(self) -> bool:
        return self.caminho.is_file()


@dataclass
class ItemRelatorio:
    numero: int
    rotulo: str
    descricao: str
    local: str
    fotos: list[Arquivo] = field(default_factory=list)
    justificativa: str = ""
    anexo: Arquivo | None = None


@dataclass
class Relatorio:
    titulo: str
    nome_arquivo: str
    subtitulo: str
    campos: list[tuple[str, str]]
    itens: list[ItemRelatorio]
    rotulo_justificativa: str
    assinaturas: list[tuple[str, str]]
    contexto: str


# --- Montagem dos dados ------------------------------------------------------------------------------

def _arquivo(sessao: Session, anexo) -> Arquivo | None:
    if anexo is None:
        return None
    autor = sessao.get(Usuario, anexo.enviado_por_id) if anexo.enviado_por_id else None
    return Arquivo(anexo.nome_original, servico_anexos.caminho(anexo), anexo.tipo_conteudo or "", anexo.criado_em, nome_do_autor(autor) if autor else "")


def _fotos(sessao: Session, bem: Bem) -> list[Arquivo]:
    """As últimas fotos do bem (a mais recente primeiro), com quem registrou e quando."""
    fotos = [a for a in (_arquivo(sessao, f.anexo) for f in bem.fotos) if a is not None and a.existe()]
    return sorted(fotos, key=lambda a: _local(a.quando) if a.quando else datetime.min.replace(tzinfo=UTC), reverse=True)[:MAXIMO_FOTOS]


def _descricao(bem: Bem) -> str:
    return " - ".join(p for p in (bem.descricao, bem.marca, bem.modelo) if p)


def _sala(bem: Bem) -> str:
    return rotulo_curto(bem.localizacao) if bem.localizacao else "—"


def _quando(valor: datetime | None) -> str:
    return _local(valor).strftime("%d/%m/%Y %H:%M") if valor else "—"


def da_classificacao(sessao: Session, lista: Classificacao) -> Relatorio:
    extraviado = lista.tipo == "extraviado"
    nome = "extraviados" if extraviado else "inserviveis"
    itens = [
        ItemRelatorio(i, item.bem.rotulo, _descricao(item.bem), _sala(item.bem), _fotos(sessao, item.bem), item.justificativa or "", _arquivo(sessao, item.anexo))
        for i, item in enumerate(lista.itens, start=1)
    ]
    campos = [("Situação da lista", STATUS.get(lista.status, lista.status)), ("Solicitante", nome_do_autor(lista.solicitante)), ("Criada em", _quando(lista.criada_em)),
              ("Enviada em", _quando(lista.enviada_em)), ("Decidida por", nome_do_autor(lista.decidido_por) if lista.decidido_por else "—"),
              ("Decidida em", _quando(lista.decidido_em)), ("Bens na lista", str(len(itens)))]
    if lista.motivo_recusa:
        campos.append(("Motivo da recusa", lista.motivo_recusa))
    titulo = "Relatório de bens extraviados" if extraviado else "Relatório de bens inservíveis"
    return Relatorio(titulo, nome, f"Lista de {'extraviados' if extraviado else 'inservíveis'} · {STATUS.get(lista.status, lista.status)} · {len(itens)} bem(ns)", campos, itens,
                     "Justificativa", [(nome_do_autor(lista.solicitante), "Solicitante"), ("", "Controle total")], f"Patrimônio · {titulo}")


def da_baixa(sessao: Session, baixa: Baixa) -> Relatorio:
    itens: list[ItemRelatorio] = []
    for i, item in enumerate(baixa.itens, start=1):
        # O anexo da baixa é o do extravio ou do inservível (a classificação aprovada mais recente do bem)
        origem = sessao.scalars(
            select(ItemClassificacao).join(Classificacao).where(ItemClassificacao.bem_id == item.bem_id, ItemClassificacao.anexo_id.is_not(None))
            .order_by(Classificacao.enviada_em.desc())
        ).first()
        motivo = f"{MOTIVOS.get(item.motivo or '', '—')} · Processo {item.processo or '—'}"
        itens.append(ItemRelatorio(i, item.bem.rotulo, _descricao(item.bem), _sala(item.bem), _fotos(sessao, item.bem), motivo,
                                   _arquivo(sessao, origem.anexo) if origem else None))
    campos = [("Situação da baixa", STATUS.get(baixa.status, baixa.status)), ("Solicitante", nome_do_autor(baixa.solicitante)), ("Criada em", _quando(baixa.criada_em)),
              ("Enviada em", _quando(baixa.enviada_em)), ("Decidida por", nome_do_autor(baixa.decidido_por) if baixa.decidido_por else "—"),
              ("Decidida em", _quando(baixa.decidido_em)), ("Bens na baixa", str(len(itens)))]
    titulo = "Relatório de baixa de bens"
    return Relatorio(titulo, "baixa", f"Baixa · {STATUS.get(baixa.status, baixa.status)} · {len(itens)} bem(ns)", campos, itens, "Motivo e processo",
                     [(nome_do_autor(baixa.solicitante), "Solicitante"), ("", "Controle total")], f"Patrimônio · {titulo}")


# --- Imagens -----------------------------------------------------------------------------------------

def _jpeg(caminho: Path, maior_lado: int) -> tuple[bytes, int, int] | None:
    """Foto reduzida para o relatório (JPEG), na orientação correta; None se o arquivo não for uma imagem legível."""
    try:
        with ImagemPil.open(caminho) as origem:
            imagem = ImageOps.exif_transpose(origem).convert("RGB")
        imagem.thumbnail((maior_lado, maior_lado))
        saida = BytesIO()
        imagem.save(saida, "JPEG", quality=82)
        return saida.getvalue(), imagem.width, imagem.height
    except Exception:  # noqa: BLE001 - arquivo ausente ou corrompido: o relatório segue sem a imagem
        return None


def _imagem_pdf(caminho: Path, caixa_largura: float, caixa_altura: float, maior_lado: int) -> Image | None:
    dados = _jpeg(caminho, maior_lado)
    if dados is None:
        return None
    conteudo, largura, altura = dados
    escala = min(caixa_largura / largura, caixa_altura / altura)
    return Image(BytesIO(conteudo), width=largura * escala, height=altura * escala)


def _eh_imagem(arquivo: Arquivo) -> bool:
    return arquivo.tipo.startswith("image/") or arquivo.caminho.suffix.lower() in (".png", ".jpg", ".jpeg")


def _eh_pdf(arquivo: Arquivo) -> bool:
    return arquivo.tipo == "application/pdf" or arquivo.caminho.suffix.lower() == ".pdf"


# --- PDF consolidado ---------------------------------------------------------------------------------

class _Link(Paragraph):
    """Parágrafo clicável: ao ser desenhado, anota onde ficou na página (o destino é ligado depois, quando as páginas finais são conhecidas)."""

    def __init__(self, conteudo: str, chave: tuple[str, int], registro: list) -> None:
        super().__init__(conteudo, ESTILO_LINK_INDICE)
        self._chave, self._registro = chave, registro

    def draw(self) -> None:
        super().draw()
        x, y = self.canv.absolutePosition(0, 0)
        self._registro.append((self._chave, self.canv.getPageNumber(), (x, y, x + self.width, y + self.height)))


def _pagina_de_fotos(rel: Relatorio, item: ItemRelatorio, autor: str) -> bytes:
    documento = DocumentoPdf(f"Fotos do item {item.numero}", f"{item.rotulo} · {item.descricao}", autor=autor)
    util = documento._largura_util()
    n = len(item.fotos)
    largura = util / n - 4 * mm
    celulas, legendas = [], []
    for foto in item.fotos:
        celulas.append(_imagem_pdf(foto.caminho, largura, 125 * mm, 1600) or texto("Imagem indisponível"))
        legendas.append(texto(f"{foto.nome}\nRegistrada em {foto.legenda()}", ESTILO_PEQUENO))
    tabela = Table([celulas, legendas], colWidths=[util / n] * n)
    tabela.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, 0), "CENTER"), ("TOPPADDING", (0, 1), (-1, 1), 4)]))
    documento.bloco(tabela)
    return documento.gerar()


def _pagina_de_imagem(titulo: str, subtitulo: str, arquivo: Arquivo, autor: str) -> bytes | None:
    documento = DocumentoPdf(titulo, subtitulo, autor=autor)
    imagem = _imagem_pdf(arquivo.caminho, documento._largura_util(), 135 * mm, 2000)
    if imagem is None:
        return None
    documento.bloco(imagem)
    return documento.gerar()


def _tabela_relatorio(rel: Relatorio, documento: DocumentoPdf, registro: list, com_anexo: bool, anexos_ok: set[int], fotos_ok: set[int]) -> Table:
    cabecalho = ["Item", "Chapa / Série", "Descrição (marca - modelo)", "Local", "Fotos (últimas)", rel.rotulo_justificativa] + (["Anexo"] if com_anexo else [])
    proporcoes = [0.6, 1.5, 3.2, 2.2, 2.9, 2.6] + ([1.2] if com_anexo else [])
    util = documento._largura_util()
    larguras = [util * p / sum(proporcoes) for p in proporcoes]
    linhas = [[Paragraph(f"<b>{c}</b>", ESTILO_PEQUENO) for c in cabecalho]]
    for item in rel.itens:
        if item.fotos:
            miniaturas = [_imagem_pdf(f.caminho, 16 * mm, 16 * mm, 300) for f in item.fotos]
            miniaturas = [m for m in miniaturas if m is not None]
            linha_fotos = Table([miniaturas], colWidths=[17 * mm] * len(miniaturas)) if miniaturas else None
            ultima = item.fotos[0]
            celula_fotos = [linha_fotos] if linha_fotos else []
            celula_fotos.append(texto(f"Última: {ultima.legenda()}", ESTILO_PEQUENO))
            if item.numero in fotos_ok:
                celula_fotos.append(_Link("<u>Ampliar fotos</u>", ("fotos", item.numero), registro))
        else:
            celula_fotos = [texto("Sem foto", ESTILO_PEQUENO)]
        linha = [texto(str(item.numero)), texto(item.rotulo, ESTILO_PEQUENO), texto(item.descricao, ESTILO_PEQUENO), texto(item.local, ESTILO_PEQUENO), celula_fotos,
                 texto(item.justificativa or "—", ESTILO_PEQUENO)]
        if com_anexo:
            linha.append(_Link(f"<u>Anexo {item.numero}</u>", ("anexo", item.numero), registro) if item.numero in anexos_ok else texto("—", ESTILO_PEQUENO))
        linhas.append(linha)
    tabela = Table(linhas, colWidths=larguras, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERMELHO_SUAVE), ("LINEBELOW", (0, 0), (-1, 0), 0.8, VERMELHO), ("LINEBELOW", (0, 1), (-1, -1), 0.3, BORDA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabela


def gerar_pdf(rel: Relatorio, autor: str, com_anexo: bool) -> bytes:
    """PDF consolidado: índice, relatório, fotos em tamanho grande e anexos (cada um com contracapa)."""
    # (etapa, título, item, partes como (conteúdo, gerado_pelo_sistema)): só o PDF enviado pelo usuário mantém o layout original
    documentos: list[tuple[str, str, int, list[tuple[bytes, bool]]]] = []
    fotos_ok, anexos_ok = set(), set()
    for item in rel.itens:
        if item.fotos:
            documentos.append(("Fotos", f"Fotos do item {item.numero} — {item.rotulo}", item.numero, [(_pagina_de_fotos(rel, item, autor), True)]))
            fotos_ok.add(item.numero)
    total_docs = len(documentos) + sum(1 for i in rel.itens if com_anexo and i.anexo and i.anexo.existe())
    for item in rel.itens:
        if not (com_anexo and item.anexo and item.anexo.existe()):
            continue
        arquivo = item.anexo
        corpo: bytes | None = None
        enviado = False
        if _eh_pdf(arquivo):
            try:
                corpo = arquivo.caminho.read_bytes()
                contar_paginas(corpo)
                enviado = True
            except Exception:  # noqa: BLE001 - PDF ilegível: fica só a contracapa avisando
                corpo = None
        elif _eh_imagem(arquivo):
            corpo = _pagina_de_imagem(f"Anexo do item {item.numero}", arquivo.nome, arquivo, autor)
        posicao = len(documentos) + 2  # o relatório é o documento 1 e as páginas de fotos já entraram
        dados = [("Item", f"{item.numero} — {item.rotulo}"), ("Arquivo", arquivo.nome), ("Registrado em", arquivo.legenda())]
        if corpo is None:
            dados.append(("Situação", "Arquivo em formato não exibível ou ilegível: não foi incluído neste consolidado."))
        capa = contracapa(f"Documento {posicao} de {total_docs + 1} · Anexo", f"Anexo do item {item.numero} — {item.rotulo}", dados, rel.contexto, autor)
        documentos.append(("Anexo", f"Anexo do item {item.numero} — {item.rotulo}", item.numero, [(capa, True)] + ([(corpo, not enviado)] if corpo else [])))
        if corpo is not None:
            anexos_ok.add(item.numero)
    # 1) Relatório (as áreas clicáveis são registradas ao desenhar)
    registro: list = []
    documento = DocumentoPdf(rel.titulo, rel.subtitulo, autor=autor)
    documento.campos(rel.campos, colunas=2).espaco(3)
    documento.bloco(_tabela_relatorio(rel, documento, registro, com_anexo, anexos_ok, fotos_ok))
    documento.assinaturas(rel.assinaturas)
    relatorio = documento.gerar()
    paginas_relatorio = contar_paginas(relatorio)
    # 2) Posições das páginas no arquivo final (o índice ocupa `k` páginas e desloca o resto; se a quantidade mudar, repete)
    deslocamento = 1
    while True:
        inicio = deslocamento + 1
        entradas = [EntradaIndice("1", "Relatório", rel.titulo, inicio, inicio + paginas_relatorio - 1)]
        pagina = inicio + paginas_relatorio
        destinos: dict[tuple[str, int], int] = {}
        for numero, (etapa, titulo, item_numero, partes) in enumerate(documentos, start=2):
            paginas = sum(contar_paginas(p) for p, _ in partes)
            entradas.append(EntradaIndice(str(numero), etapa, titulo, pagina, pagina + paginas - 1))
            destinos[("fotos" if etapa == "Fotos" else "anexo", item_numero)] = pagina
            pagina += paginas
        indice, links = indice_consolidado("Índice do relatório consolidado", rel.contexto, entradas, autor)
        if contar_paginas(indice) == deslocamento:
            break
        deslocamento = contar_paginas(indice)
    for chave, pagina_origem, retangulo in registro:
        if chave in destinos:
            links.append(AlvoLink(deslocamento + pagina_origem, retangulo, destinos[chave]))
    partes_finais: list[tuple[bytes, bool]] = [(indice, True), (relatorio, True)]
    for _, _, _, partes in documentos:
        partes_finais.extend(partes)
    marcadores = [("Índice", 1)] + [(f"{e.numero}. {e.titulo}", e.pagina_inicial) for e in entradas]
    return montar_consolidado(partes_finais, links=links, marcadores=marcadores)


# --- Excel -------------------------------------------------------------------------------------------

def gerar_xlsx(rel: Relatorio, com_anexo: bool) -> bytes:
    livro = Workbook()
    folha = livro.active
    folha.title = "Relatório"
    vermelho, suave = "C82331", "FCECEE"
    folha.cell(row=1, column=1, value=rel.titulo).font = Font(bold=True, size=13, color=vermelho)
    folha.cell(row=2, column=1, value=rel.subtitulo).font = Font(color="586372")
    colunas = [("Item", 6), ("Chapa / Série", 18), ("Descrição (marca - modelo)", 46), ("Local", 32), ("Fotos (últimas)", 24), (rel.rotulo_justificativa, 38)] + ([("Anexo", 34)] if com_anexo else [])
    linha_cab = 4
    for indice, (titulo, largura) in enumerate(colunas, start=1):
        c = folha.cell(row=linha_cab, column=indice, value=titulo)
        c.font, c.fill = Font(bold=True), PatternFill("solid", fgColor=suave)
        c.border, c.alignment = Border(bottom=Side(style="thin", color=vermelho)), Alignment(vertical="center", wrap_text=True)
        folha.column_dimensions[get_column_letter(indice)].width = largura
    folha.freeze_panes = folha.cell(row=linha_cab + 1, column=1)
    # Aba com as fotos grandes (datas, horas e quem registrou); cada item com fotos tem um bloco
    fotos = livro.create_sheet("Fotos")
    fotos.column_dimensions["A"].width = 60
    fotos.cell(row=1, column=1, value="Fotos dos bens (em tamanho grande)").font = Font(bold=True, size=13, color=vermelho)
    linha_foto, ancora_fotos = 3, {}
    for item in rel.itens:
        if not item.fotos:
            continue
        ancora_fotos[item.numero] = linha_foto
        fotos.cell(row=linha_foto, column=1, value=f"Item {item.numero} — {item.rotulo} — {item.descricao}").font = Font(bold=True)
        linha_foto += 1
        for foto in item.fotos:
            dados = _jpeg(foto.caminho, 900)
            fotos.cell(row=linha_foto, column=1, value=f"{foto.nome} · registrada em {foto.legenda()}").font = Font(color="586372")
            linha_foto += 1
            if dados is None:
                fotos.cell(row=linha_foto, column=1, value="Imagem indisponível")
                linha_foto += 2
                continue
            imagem = ImagemExcel(BytesIO(dados[0]))
            escala = min(1.0, 420 / dados[2])
            imagem.width, imagem.height = int(dados[1] * escala), int(dados[2] * escala)
            fotos.add_image(imagem, f"A{linha_foto}")
            linha_foto += int(imagem.height / 20) + 2
        linha_foto += 1
    linha = linha_cab
    for item in rel.itens:
        linha += 1
        valores = [item.numero, item.rotulo, item.descricao, item.local, None, item.justificativa or "—"]
        for indice, valor in enumerate(valores, start=1):
            c = folha.cell(row=linha, column=indice, value=valor)
            c.alignment = Alignment(vertical="top", wrap_text=True)
        celula = folha.cell(row=linha, column=5)
        if item.fotos:
            folha.row_dimensions[linha].height = 84
            miniatura = _jpeg(item.fotos[0].caminho, 240)
            if miniatura is not None:
                imagem = ImagemExcel(BytesIO(miniatura[0]))
                escala = min(1.0, 70 / miniatura[2], 150 / miniatura[1])
                imagem.width, imagem.height = int(miniatura[1] * escala), int(miniatura[2] * escala)
                folha.add_image(imagem, f"E{linha}")
            celula.value = f"Ampliar ({len(item.fotos)}) · {item.fotos[0].legenda()}"
            celula.hyperlink = Hyperlink(ref=celula.coordinate, location=f"'Fotos'!A{ancora_fotos[item.numero]}", display=celula.value)
            celula.font = Font(color="1A56A0", underline="single", size=8)
            celula.alignment = Alignment(vertical="bottom", wrap_text=True)
        else:
            celula.value = "Sem foto"
        if com_anexo:
            folha.cell(row=linha, column=7, value=(item.anexo.nome if item.anexo else "—")).alignment = Alignment(vertical="top", wrap_text=True)
    folha.cell(row=linha + 2, column=1, value="Os anexos (boletim de ocorrência, e-mail, foto) seguem no PDF consolidado, que tem links para cada um.").font = Font(italic=True, color="586372")
    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()


# --- Entradas públicas -------------------------------------------------------------------------------

def _nome(rel: Relatorio, sufixo: str, hoje: str) -> str:
    return f"relatorio-{rel.nome_arquivo}-{hoje}.{sufixo}"


def relatorio_da_classificacao(sessao: Session, lista: Classificacao, formato: str, autor: Usuario, hoje: str) -> tuple[bytes, str, str]:
    rel = da_classificacao(sessao, lista)
    return _saida(rel, formato, autor, hoje)


def relatorio_da_baixa(sessao: Session, baixa: Baixa, formato: str, autor: Usuario, hoje: str) -> tuple[bytes, str, str]:
    rel = da_baixa(sessao, baixa)
    return _saida(rel, formato, autor, hoje)


def _saida(rel: Relatorio, formato: str, autor: Usuario, hoje: str) -> tuple[bytes, str, str]:
    if formato not in ("pdf", "xlsx"):
        raise ErroPatrimonio("Formato inválido: use pdf ou xlsx.")
    if formato == "xlsx":
        return gerar_xlsx(rel, True), _nome(rel, "xlsx", hoje), XLSX
    return gerar_pdf(rel, nome_do_autor(autor), True), _nome(rel, "pdf", hoje), "application/pdf"
