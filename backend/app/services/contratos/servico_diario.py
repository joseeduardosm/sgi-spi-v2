# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras do diário de bordo do contrato: registro, glosas e PDF.
"""Diário de bordo do contrato.

A equipe (criador, integrantes vigentes ou SuperRoot) relata ocorrências da execução. Uma ocorrência
pode implicar glosa de itens do contrato; as glosas valem na competência cujo período contém a data da
ocorrência e limitam o que pode ser medido nela. As ocorrências não são editadas nem excluídas.

A ocorrência pode ter até 5 anexos (enviados também no e-mail) e pode impactar a avaliação da qualidade:
fica ligada a itens do formulário de avaliação ativo, que na avaliação da competência do período exigem
justificativa para a nota máxima (`itens_impactados`).
"""

import unicodedata
import uuid
from collections import defaultdict
from io import BytesIO
from datetime import UTC, date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.tarefas.descricao import texto_da_descricao
from app.core.banco import agora_utc
from app.models.contratos import AnexoOcorrencia, Competencia, Contrato, GlosaOcorrencia, ItemAvaliacaoOcorrencia, OcorrenciaDiario
from app.models.usuario import Usuario
from app.schemas.contratos.diario import (
    DiarioContrato,
    EnvioEmail,
    GravacaoOcorrencia,
    LeituraAnexoOcorrencia,
    LeituraGlosa,
    LeituraItemAvaliacao,
    LeituraOcorrencia,
    OpcaoItemAvaliacao,
    OpcaoCompetenciaDiario,
    OpcaoItemGlosa,
)
from app.services import servico_anexos
from app.services.contratos.documentos_execucao import PAPEIS, data_hora, quantidade
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_contratos import designacoes_vigentes, exigir_edicao, hoje, obter_contrato, pode_editar
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, Spacer
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image

from app.services.documentos.pdf import (BORDA, ESTILO_PEQUENO, ESTILO_ROTULO, ESTILO_TITULO, DocumentoPdf, abrir_pdf, contar_paginas, contracapa,
                                          montar_consolidado, texto)
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)
MAXIMO_ANEXOS = 5


def competencia_da_data(contrato: Contrato, dia: date) -> Competencia | None:
    """Competência regular cujo período contém o dia (onde as glosas daquela data valem)."""
    return next((c for c in contrato.competencias if c.tipo == "regular" and c.periodo_inicio <= dia <= c.periodo_fim), None)


def ocorrencias_do_periodo(contrato: Contrato, inicio: date | None, fim: date | None) -> list[OcorrenciaDiario]:
    """Ocorrências com data dentro do período (limites inclusivos; vazio = sem limite)."""
    return sorted(
        (o for o in contrato.ocorrencias if (inicio is None or o.data_ocorrencia >= inicio) and (fim is None or o.data_ocorrencia <= fim)),
        key=lambda o: (o.data_ocorrencia, o.criado_em.replace(tzinfo=None)),
    )


def competencia_da_ocorrencia(contrato: Contrato, ocorrencia: OcorrenciaDiario) -> Competencia | None:
    """Competência regular afetada pela ocorrência: a apontada no registro ou, nos registros antigos, a que contém a data."""
    if ocorrencia.competencia_afetada is not None:
        return next((c for c in contrato.competencias if c.tipo == "regular" and c.competencia == ocorrencia.competencia_afetada), None)
    return competencia_da_data(contrato, ocorrencia.data_ocorrencia)


def ocorrencias_da_competencia(contrato: Contrato, competencia: Competencia) -> list[OcorrenciaDiario]:
    """Ocorrências que **afetam** a competência (a glosa vale nela e o impacto pesa na avaliação dela), mesmo que a data seja de outro mês."""
    if competencia.tipo != "regular":
        return []
    return sorted(
        (o for o in contrato.ocorrencias if (o.competencia_afetada == competencia.competencia if o.competencia_afetada is not None
                                             else competencia.periodo_inicio <= o.data_ocorrencia <= competencia.periodo_fim)),
        key=lambda o: (o.data_ocorrencia, o.criado_em.replace(tzinfo=None)),
    )


def glosas_da_competencia(contrato: Contrato, competencia: Competencia, trecho: tuple[date, date] | None = None) -> dict[uuid.UUID, Decimal]:
    """Quantidade glosada por item nas ocorrências que afetam a competência.

    Competência com mais de um trecho (mês com virada de preço): a glosa vai ao trecho da data; a de data fora da competência
    (afeta outro mês) vai ao primeiro trecho.
    """
    trechos = sorted({(i.periodo_inicio or competencia.periodo_inicio, i.periodo_fim or competencia.periodo_fim) for i in competencia.itens})
    total: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for ocorrencia in ocorrencias_da_competencia(contrato, competencia):
        if trecho is not None and len(trechos) > 1:
            dentro = competencia.periodo_inicio <= ocorrencia.data_ocorrencia <= competencia.periodo_fim
            if dentro and not (trecho[0] <= ocorrencia.data_ocorrencia <= trecho[1]):
                continue
            if not dentro and trecho != trechos[0]:
                continue
        for glosa in ocorrencia.glosas:
            total[glosa.item_id] += glosa.quantidade
    return dict(total)


def _papel(contrato: Contrato, autor: Usuario) -> str:
    """Papel de quem registra: o da designação vigente, ou vazio (criador/SuperRoot fora da equipe)."""
    return next((d.papel for d in designacoes_vigentes(contrato) if d.usuario_id == autor.id), "")


def itens_do_formulario_ativo(contrato: Contrato) -> list[OpcaoItemAvaliacao]:
    """Itens do formulário de avaliação ativo do contrato (vazio sem formulário ativo)."""
    from app.services.contratos.servico_configuracao_execucao import formulario_ativo
    formulario = formulario_ativo(contrato)
    if formulario is None:
        return []
    return [OpcaoItemAvaliacao(id=item["id"], nome=item["nome"], grupo=grupo["nome"])
            for grupo in formulario.definicao.get("grupos", []) for item in grupo.get("itens", [])]


def registrar(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoOcorrencia, autor: Usuario,
              arquivos: list[tuple[str, bytes]] | None = None) -> OcorrenciaDiario:
    """Registra a ocorrência (glosas, anexos e itens de avaliação impactados). O e-mail à equipe e ao preposto é
    enviado depois, em segundo plano."""
    arquivos = arquivos or []
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    if dados.data_ocorrencia > hoje():
        raise ErroRegraContrato("A data da ocorrência não pode ser futura.")
    if dados.data_ocorrencia < contrato.data_inicio:
        raise ErroRegraContrato(f"A data da ocorrência é anterior ao início do contrato ({contrato.data_inicio:%d/%m/%Y}).")
    afetada = None
    if dados.competencia_afetada:
        afetada = next((c for c in contrato.competencias if c.tipo == "regular" and f"{c.competencia:%Y-%m}" == dados.competencia_afetada), None)
        if afetada is None:
            raise ErroRegraContrato("A competência afetada não existe neste contrato: escolha uma das competências geradas.")
    else:
        afetada = competencia_da_data(contrato, dados.data_ocorrencia)
    itens = {i.id: i for i in contrato.itens}
    for glosa in dados.glosas:
        if glosa.item_id not in itens:
            raise ErroRegraContrato("A glosa aponta para um item que não é deste contrato.")
    if len(arquivos) > MAXIMO_ANEXOS:
        raise ErroRegraContrato(f"Anexe no máximo {MAXIMO_ANEXOS} arquivos por ocorrência.")
    if sum(len(c) for _, c in arquivos) > servico_anexos.tamanho_maximo():
        raise ErroRegraContrato("Os anexos somados passam do tamanho máximo permitido.")
    itens_avaliacao = []
    if dados.impacta_avaliacao:
        opcoes = {o.id: o for o in itens_do_formulario_ativo(contrato)}
        if not opcoes:
            raise ErroRegraContrato("O contrato não tem formulário de avaliação ativo: não há itens para marcar o impacto.")
        for item_id in dados.itens_avaliacao:
            if item_id not in opcoes:
                raise ErroRegraContrato("O item de avaliação escolhido não é do formulário ativo do contrato.")
            itens_avaliacao.append(ItemAvaliacaoOcorrencia(item_id=item_id, item_nome=opcoes[item_id].nome[:500], grupo_nome=opcoes[item_id].grupo[:500]))
    anexos = []
    for ordem, (nome, conteudo) in enumerate(arquivos):
        try:
            anexo = servico_anexos.guardar_arquivo(sessao, BytesIO(conteudo), nome, "contrato-diario-anexo", autor.id)
        except servico_anexos.ErroAnexo as erro:
            raise ErroRegraContrato(f"{nome}: {erro}") from erro
        anexo.contrato_id = contrato.id
        anexos.append(AnexoOcorrencia(anexo_id=anexo.id, ordem=ordem))
    ocorrencia = OcorrenciaDiario(
        data_ocorrencia=dados.data_ocorrencia, competencia_afetada=afetada.competencia if afetada else None, descricao=dados.descricao, possui_glosa=dados.possui_glosa,
        impacta_avaliacao=dados.impacta_avaliacao, itens_avaliacao=itens_avaliacao, anexos=anexos,
        registrada_por_id=autor.id, registrada_por_nome=autor.nome_completo or autor.login, registrada_por_papel=_papel(contrato, autor),
        criado_em=agora_utc(),
        glosas=[GlosaOcorrencia(item_id=g.item_id, descricao_item=itens[g.item_id].descricao, quantidade=g.quantidade) for g in dados.glosas],
    )
    contrato.ocorrencias.append(ocorrencia)
    sessao.flush()
    auditar(
        sessao, autor.login, "contrato.diario.registrar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
        alvo_id=contrato.id,
        dados={"ocorrencia": ocorrencia.id, "data": dados.data_ocorrencia, "glosas": [{"item": str(g.item_id), "quantidade": g.quantidade} for g in dados.glosas],
               "anexos": [nome for nome, _ in arquivos], "itens_avaliacao": dados.itens_avaliacao},
    )
    from app.services.contratos import avisos
    avisos.ocorrencia_registrada(sessao, contrato, ocorrencia, autor)
    sessao.commit()
    return ocorrencia


def registrar_pendencia_cadin(sessao: Session, contrato: Contrato, competencia: Competencia, consulta, autor: Usuario) -> OcorrenciaDiario:
    """Ocorrência automática do diário de bordo para uma pendência registrada na etapa de CADIN.

    Tem a **mesma data e hora** do registro da consulta (`consulta.criado_em`), vale para a competência da etapa (se regular) e leva a descrição
    da pendência. Não gera glosa, não impacta a avaliação e não envia e-mail próprio (a equipe já recebe em cópia o e-mail ao preposto).
    Sem validação de data: a pendência é registrada quando acontece.
    """
    from html import escape
    from app.core.banco import FUSO_SAO_PAULO

    quando = consulta.criado_em
    # Instante sem fuso (SQLite) é UTC, como tudo o que o sistema grava; a data da ocorrência é a de São Paulo
    momento = (quando if quando.tzinfo else quando.replace(tzinfo=UTC)).astimezone(FUSO_SAO_PAULO)
    relato = (f"<p><strong>Pendência no CADIN</strong> registrada na etapa de CADIN da competência {competencia.competencia:%m/%Y} "
              f"em {momento:%d/%m/%Y} às {momento:%H:%M}.</p><p><strong>Pendência:</strong> {escape(consulta.pendencia)}</p>")
    ocorrencia = OcorrenciaDiario(
        data_ocorrencia=momento.date(), competencia_afetada=competencia.competencia if competencia.tipo == "regular" else None, descricao=relato,
        possui_glosa=False, impacta_avaliacao=False,
        registrada_por_id=autor.id, registrada_por_nome=autor.nome_completo or autor.login, registrada_por_papel=_papel(contrato, autor),
        criado_em=quando,
    )
    contrato.ocorrencias.append(ocorrencia)
    sessao.flush()
    auditar(sessao, autor.login, "contrato.diario.registrar", f"Contrato {contrato.numero}", "Pendência no CADIN", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"ocorrencia": ocorrencia.id, "origem": "cadin", "competencia": f"{competencia.competencia:%Y-%m}"})
    return ocorrencia


def obter_ocorrencia(contrato: Contrato, ocorrencia_id: uuid.UUID) -> OcorrenciaDiario:
    """Ocorrência do contrato pelo id, ou 404."""
    ocorrencia = next((o for o in contrato.ocorrencias if o.id == ocorrencia_id), None)
    if ocorrencia is None:
        raise RegistroNaoEncontrado("Ocorrência")
    return ocorrencia


def leitura(contrato: Contrato, ocorrencia: OcorrenciaDiario) -> LeituraOcorrencia:
    """Ocorrência no formato da API, com a competência da data e o estado do e-mail."""
    competencia = competencia_da_ocorrencia(contrato, ocorrencia)
    return LeituraOcorrencia(
        id=ocorrencia.id, data_ocorrencia=ocorrencia.data_ocorrencia, descricao=ocorrencia.descricao, possui_glosa=ocorrencia.possui_glosa,
        glosas=[LeituraGlosa(item_id=g.item_id, descricao_item=g.descricao_item, quantidade=g.quantidade) for g in ocorrencia.glosas],
        anexos=[LeituraAnexoOcorrencia(id=a.anexo.id, nome=a.anexo.nome_original, tamanho=a.anexo.tamanho, tipo=a.anexo.tipo_conteudo)
                for a in ocorrencia.anexos],
        impacta_avaliacao=ocorrencia.impacta_avaliacao,
        itens_avaliacao=[LeituraItemAvaliacao(item_id=i.item_id, item_nome=i.item_nome, grupo_nome=i.grupo_nome) for i in ocorrencia.itens_avaliacao],
        registrada_por_id=ocorrencia.registrada_por_id, registrada_por_nome=ocorrencia.registrada_por_nome,
        registrada_por_papel=ocorrencia.registrada_por_papel, criado_em=ocorrencia.criado_em,
        competencia_rotulo=competencia.numero_competencia if competencia else None,
        competencia_afetada=f"{competencia.competencia:%Y-%m}" if competencia else None,
        # Só avisa quando a glosa chegou depois da conclusão (as anteriores já entraram na medição)
        medicao_ja_concluida=bool(
            ocorrencia.possui_glosa and competencia and competencia.medicao_concluida_em
            and ocorrencia.criado_em > competencia.medicao_concluida_em
        ),
        email=EnvioEmail(enviado_em=ocorrencia.email_enviado_em, ok=ocorrencia.email_ok,
                         destinatarios=ocorrencia.email_destinatarios or [], erro=ocorrencia.email_erro),
    )


def diario(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> DiarioContrato:
    """Diário completo do contrato, se o usuário pode registrar e os itens para o combobox da glosa."""
    contrato = obter_contrato(sessao, contrato_id)
    return DiarioContrato(
        ocorrencias=[leitura(contrato, o) for o in contrato.ocorrencias],
        pode_registrar=pode_editar(sessao, contrato, usuario),
        itens=[OpcaoItemGlosa(id=i.id, ordem=i.ordem, descricao=i.descricao, tipo=i.tipo) for i in contrato.itens],
        itens_avaliacao=itens_do_formulario_ativo(contrato),
        competencias=[OpcaoCompetenciaDiario(identificador=f"{c.competencia:%Y-%m}", rotulo=c.numero_competencia, periodo_inicio=c.periodo_inicio,
                                             periodo_fim=c.periodo_fim, medicao_concluida=c.medicao_concluida_em is not None)
                      for c in sorted((c for c in contrato.competencias if c.tipo == "regular"), key=lambda c: c.competencia, reverse=True)],
    )


def anexo_da_ocorrencia(contrato: Contrato, ocorrencia_id: uuid.UUID, anexo_id: uuid.UUID):
    """Arquivo anexado a uma ocorrência do contrato, ou 404."""
    ocorrencia = obter_ocorrencia(contrato, ocorrencia_id)
    vinculo = next((a for a in ocorrencia.anexos if a.anexo_id == anexo_id), None)
    if vinculo is None:
        raise RegistroNaoEncontrado("Anexo")
    return vinculo.anexo


def _chave_nome(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().strip().lower()


def ocorrencias_que_impactam(contrato: Contrato, competencia: Competencia) -> list[OcorrenciaDiario]:
    """Ocorrências marcadas como "impacta a avaliação" que afetam a competência (a apontada no registro, não a da data)."""
    return [o for o in ocorrencias_da_competencia(contrato, competencia) if o.impacta_avaliacao]


def itens_impactados(contrato: Contrato, competencia: Competencia, definicao: dict) -> dict[str, list[OcorrenciaDiario]]:
    """{id do item do formulário da competência: ocorrências que o impactam}.

    O vínculo é pelo id do item; se o formulário da competência for de outra versão (ids diferentes), vale o nome do item.
    """
    por_id = {item["id"]: item for grupo in definicao.get("grupos", []) for item in grupo.get("itens", [])}
    por_nome = {_chave_nome(item["nome"]): item_id for item_id, item in por_id.items()}
    resultado: dict[str, list[OcorrenciaDiario]] = defaultdict(list)
    for ocorrencia in ocorrencias_que_impactam(contrato, competencia):
        for vinculo in ocorrencia.itens_avaliacao:
            item_id = vinculo.item_id if vinculo.item_id in por_id else por_nome.get(_chave_nome(vinculo.item_nome))
            if item_id and ocorrencia not in resultado[item_id]:
                resultado[item_id].append(ocorrencia)
    return dict(resultado)



def _relato_com_marcas(o) -> str:
    """Relato em texto puro; "Haverá glosa" e "Impacta a avaliação da qualidade" só aparecem quando a resposta é Sim."""
    linhas = [texto_da_descricao(o.descricao)]
    if o.competencia_afetada is not None:
        linhas.append(f"Competência afetada: {o.competencia_afetada:%m/%Y}")
    if o.possui_glosa:
        linhas.append("Haverá glosa: " + "; ".join(f"{g.descricao_item}: {quantidade(g.quantidade)}" for g in o.glosas))
    if o.impacta_avaliacao:
        linhas.append("Impacta a avaliação da qualidade: " + "; ".join(i.item_nome for i in o.itens_avaliacao))
    return "\n".join(linhas)

DIAS_DA_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
MESES_POR_EXTENSO = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


ESTILO_DIA = ParagraphStyle("dia_diario", parent=ESTILO_TITULO, fontSize=16, leading=20, spaceAfter=2)


def _dia_por_extenso(dia: date) -> str:
    return f"{DIAS_DA_SEMANA[dia.weekday()].capitalize()}, {dia.day} de {MESES_POR_EXTENSO[dia.month - 1]} de {dia.year}"


class _AnexoDoDiario:
    """Anexo de uma ocorrência na ordem em que entra no fim do PDF (número, data da ocorrência, arquivo e onde fica no PDF)."""

    def __init__(self, numero: int, ocorrencia: OcorrenciaDiario, anexo) -> None:
        self.numero, self.ocorrencia, self.anexo = numero, ocorrencia, anexo
        self.paginas = "—"


def _paginas_do_anexo(anexo) -> bytes | None:
    """PDF com o conteúdo do anexo: o PDF entra como está e a imagem vira uma página; os demais formatos (Office, TXT, CSV) não saem aqui (None)."""
    caminho = servico_anexos.caminho(anexo)
    if not caminho.is_file():
        return None
    if anexo.tipo_conteudo == servico_anexos.TIPO_PDF:
        conteudo = caminho.read_bytes()
        try:
            len(abrir_pdf(conteudo).pages)
        except Exception:  # noqa: BLE001 — PDF corrompido ou com senha não pode impedir o diário
            return None
        return conteudo
    if anexo.tipo_conteudo in ("image/png", "image/jpeg"):
        try:
            leitor = ImageReader(str(caminho))
            largura, altura = leitor.getSize()
            caixa_l, caixa_a = landscape(A4)[0] - 30 * mm, landscape(A4)[1] - 40 * mm
            escala = min(caixa_l / largura, caixa_a / altura, 1.0) if largura and altura else 1.0
            documento = DocumentoPdf("Anexo", paisagem=True)
            documento.bloco(Image(str(caminho), width=largura * escala, height=altura * escala))
            return documento.gerar()
        except Exception:  # noqa: BLE001 — imagem ilegível
            return None
    return None


def gerar_pdf(contrato: Contrato, inicio: date | None = None, fim: date | None = None, autor: str = "") -> bytes:
    """Diário de bordo em PDF (A4 paisagem). Os anexos das ocorrências são juntados **no fim**, numa lista de anexos:
    depois do diário vem a lista (nº, ocorrência, arquivo e páginas) e, em seguida, cada anexo precedido de uma folha de rosto.
    Todas as páginas saem numeradas em sequência ("Página X de N").
    """
    ocorrencias = ocorrencias_do_periodo(contrato, inicio, fim)
    anexos = [_AnexoDoDiario(n, o, a.anexo) for n, (o, a) in enumerate(((o, a) for o in ocorrencias for a in o.anexos), start=1)]
    periodo = _rotulo_periodo(inicio, fim)
    if not anexos:
        return _diario_pdf(contrato, inicio, fim, autor, ocorrencias, [])
    contexto = f"Diário de bordo · Contrato {contrato.numero} · {periodo}"
    # Primeira volta: descobre quantas páginas tem o diário com a lista (a coluna "Páginas" ocupa o mesmo espaço)
    paginas_diario = contar_paginas(_diario_pdf(contrato, inicio, fim, autor, ocorrencias, anexos))
    partes: list[tuple[bytes, bool]] = []
    proxima = paginas_diario + 1
    for item in anexos:
        quem = f"{item.ocorrencia.registrada_por_nome}, em {data_hora(item.ocorrencia.criado_em)}"
        pares = [("Ocorrência de", f"{item.ocorrencia.data_ocorrencia:%d/%m/%Y}"), ("Registrada por", quem), ("Arquivo", item.anexo.nome_original)]
        conteudo = _paginas_do_anexo(item.anexo)
        capa = contracapa(f"Anexo {item.numero} de {len(anexos)}", item.anexo.nome_original,
                          pares if conteudo is not None else pares + [("Atenção", "Este formato não é exibido dentro do PDF: baixe o arquivo no diário de bordo do sistema.")],
                          contexto, autor)
        paginas = 1 + (contar_paginas(conteudo) if conteudo is not None else 0)
        item.paginas = f"{proxima} a {proxima + paginas - 1}" if paginas > 1 else f"{proxima}"
        proxima += paginas
        partes.append((capa, True))
        if conteudo is not None:
            partes.append((conteudo, False))
    principal = _diario_pdf(contrato, inicio, fim, autor, ocorrencias, anexos)
    return montar_consolidado([(principal, True), *partes], marcadores=[("Diário de bordo", 1), ("Lista de anexos", paginas_diario)])


def _rotulo_periodo(inicio: date | None, fim: date | None) -> str:
    return (
        f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}" if inicio and fim
        else f"desde {inicio:%d/%m/%Y}" if inicio else f"até {fim:%d/%m/%Y}" if fim else "todo o contrato"
    )


def _diario_pdf(contrato: Contrato, inicio: date | None, fim: date | None, autor: str, ocorrencias: list[OcorrenciaDiario], anexos: list) -> bytes:
    """Diário de bordo em PDF (A4 paisagem), em formato de diário: **uma página por dia com ocorrência**, com todas as ocorrências do dia.

    Dias sem ocorrência não geram página. Um dia com muito texto continua nas páginas seguintes (a quebra é do conteúdo, não da linha).
    """
    periodo = _rotulo_periodo(inicio, fim)
    documento = DocumentoPdf("Diário de bordo", f"Contrato {contrato.numero} · {periodo}", paisagem=True, autor=autor)
    identificacao = (f"Contratada: {contrato.empresa.razao_social}  ·  Processo SEI (execução): {contrato.sei_execucao_numero or '—'}"
                     f"  ·  Objeto: {contrato.objeto or '—'}")
    if not ocorrencias:
        documento.secao("Ocorrências").paragrafo("Nenhuma ocorrência registrada no período.")
        return documento.gerar()

    por_dia: dict[date, list[OcorrenciaDiario]] = defaultdict(list)
    for o in ocorrencias:
        por_dia[o.data_ocorrencia].append(o)
    traco = HRFlowable(width="100%", thickness=0.5, color=BORDA, spaceBefore=6, spaceAfter=6)
    for numero_dia, (dia, do_dia) in enumerate(sorted(por_dia.items())):
        if numero_dia:
            documento.bloco(PageBreak())
        documento.bloco(Paragraph(escape(_dia_por_extenso(dia)), ESTILO_DIA),
                        Paragraph(f"{len(do_dia)} ocorrência(s) · {escape(identificacao)}", ESTILO_PEQUENO), Spacer(1, 4 * mm))
        for posicao, o in enumerate(do_dia, start=1):
            quem = o.registrada_por_nome + (f" ({PAPEIS.get(o.registrada_por_papel, o.registrada_por_papel)})" if o.registrada_por_papel else "")
            marcas = []
            if o.competencia_afetada is not None:
                marcas.append(f"Competência afetada: {o.competencia_afetada:%m/%Y}")
            if o.possui_glosa:
                marcas.append("Haverá glosa: " + "; ".join(f"{g.descricao_item}: {quantidade(g.quantidade)}" for g in o.glosas))
            if o.impacta_avaliacao:
                marcas.append("Impacta a avaliação da qualidade: " + "; ".join(i.item_nome for i in o.itens_avaliacao))
            if o.anexos:
                marcas.append("Anexos: " + "; ".join(a.anexo.nome_original for a in o.anexos))
            blocos = [Paragraph(f"Ocorrência {posicao} · registrada por {escape(quem)} em {escape(data_hora(o.criado_em))}", ESTILO_ROTULO),
                      Spacer(1, 1.5 * mm), texto(texto_da_descricao(o.descricao))]
            blocos += [Paragraph(escape(m), ESTILO_PEQUENO) for m in marcas]
            documento.bloco(*blocos, traco)

    # Totais por item, para conferência com a medição (em página própria, depois do último dia)
    totais: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for o in ocorrencias:
        for g in o.glosas:
            totais[g.descricao_item] += g.quantidade
    if totais:
        documento.bloco(PageBreak())
        documento.secao("Glosas por item").tabela(
            ["Item", "Quantidade glosada"], [[item, quantidade(q)] for item, q in sorted(totais.items())], larguras=[8, 2], alinhar_direita=[1]
        )
    if anexos:
        # Lista de anexos no fim: cada arquivo vem logo depois do diário, com uma folha de rosto
        documento.bloco(PageBreak())
        documento.secao(f"Lista de anexos ({len(anexos)})").paragrafo("Os arquivos anexados às ocorrências seguem nas páginas indicadas, cada um precedido de uma folha de rosto.")
        documento.tabela(
            ["Nº", "Ocorrência de", "Arquivo", "Páginas"],
            [[str(a.numero), f"{a.ocorrencia.data_ocorrencia:%d/%m/%Y}", a.anexo.nome_original, a.paginas] for a in anexos],
            larguras=[0.6, 1.6, 8, 1.8],
        )
    return documento.gerar()
