# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar os PDFs da execução (memória de cálculo, avaliação e consolidado).
"""PDFs da execução: memória de cálculo da medição, relatório de avaliação e documento consolidado.

Também reúne formatadores usados em outros PDFs do módulo (moeda, quantidade, data/hora e nomes
dos papéis da equipe).
"""

from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader

from app.models.anexo import Anexo
from app.models.contratos import Competencia, Contrato, NotaEmpenho
from app.services import servico_anexos
from app.services.contratos.calculos import arredondar
from app.services.documentos.pdf import FUSO_SAO_PAULO, DocumentoPdf, contar_paginas, contracapa, montar_consolidado

# Nomes dos papéis da equipe como aparecem nos documentos
PAPEIS = {
    "gestor": "Gestor",
    "gestor_suplente": "Suplente do gestor",
    "fiscal_administrativo": "Fiscal administrativo",
    "fiscal_administrativo_suplente": "Suplente administrativo",
    "fiscal_tecnico": "Fiscal técnico",
    "fiscal_tecnico_suplente": "Suplente técnico",
}


def moeda(valor: Decimal | None) -> str:
    """Valor em reais no formato brasileiro (R$ 1.234,56); vazio vira "R$ -"."""
    if valor is None:
        return "R$ -"
    texto = f"{arredondar(Decimal(valor)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def quantidade(valor: Decimal) -> str:
    """Até 4 casas, sem zeros à direita, no formato brasileiro (ex.: 1.234,5)."""
    texto = f"{Decimal(valor):,.4f}".rstrip("0").rstrip(".")
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def data_hora(valor) -> str:
    """Data e hora no horário de Brasília (dd/mm/aaaa hh:mm), ou "—" se vazio."""
    return valor.astimezone(FUSO_SAO_PAULO).strftime("%d/%m/%Y %H:%M") if valor else "—"


def _cabecalho_contrato(documento: DocumentoPdf, contrato: Contrato, competencia: Competencia) -> None:
    """Seção "Identificação" comum aos documentos da competência."""
    documento.secao("Identificação").campos(
        [
            ("Contrato", contrato.numero),
            ("Competência", f"{competencia.competencia:%m/%Y}"),
            ("Contratada", contrato.empresa.razao_social),
            ("Período", f"{competencia.periodo_inicio:%d/%m/%Y} a {competencia.periodo_fim:%d/%m/%Y}"),
            ("Objeto", contrato.objeto),
            ("Processo SEI (execução)", contrato.sei_execucao_numero),
        ]
    )


def memoria_medicao(contrato: Contrato, competencia: Competencia, notas: list[NotaEmpenho], versao: int, autor: str) -> bytes:
    """PDF da memória de cálculo: itens medidos, NEs escolhidas e ciências."""
    documento = DocumentoPdf(
        "Memória de cálculo da medição", f"Contrato {contrato.numero} · Competência {competencia.competencia:%m/%Y} · versão {versao}",
        paisagem=True, autor=autor,
    )
    # Importação local: servico_competencias e servico_diario também importam este módulo
    from app.services.contratos.servico_competencias import saldos_da_medicao
    from app.services.contratos.servico_diario import ocorrencias_do_periodo

    _cabecalho_contrato(documento, contrato, competencia)
    saldos = saldos_da_medicao(contrato, competencia)
    # Uma linha por item, somando o total medido
    total = Decimal(0)
    linhas = []
    for item in competencia.itens:
        subtotal = arredondar(item.quantidade_medida * item.valor_unitario)
        total += subtotal
        saldo = saldos[item.id]
        linhas.append(
            [str(item.ordem), item.descricao, "Contínuo" if item.tipo == "continuo" else "Sob demanda", moeda(item.valor_unitario),
             quantidade(saldo.saldo), quantidade(saldo.glosas), quantidade(saldo.saldo_liquido), quantidade(item.quantidade_medida), moeda(subtotal)]
        )
    documento.secao("Medição do serviço").tabela(
        ["Item", "Descrição", "Tipo", "Valor unitário", "Saldo", "Glosas", "Saldo líquido", "Medição", "Subtotal"], linhas,
        larguras=[0.5, 4.4, 1.2, 1.4, 1.1, 1.1, 1.2, 1.1, 1.5], alinhar_direita=[3, 4, 5, 6, 7, 8],
        rodape=["", "Total medido", "", "", "", "", "", "", moeda(total)],
    )
    # Glosas do diário de bordo que valem nesta competência (data no período)
    glosas = [
        [f"{o.data_ocorrencia:%d/%m/%Y}", o.registrada_por_nome, o.descricao if len(o.descricao) <= 300 else o.descricao[:297] + "…",
         g.descricao_item, quantidade(g.quantidade)]
        for o in (ocorrencias_do_periodo(contrato, competencia.periodo_inicio, competencia.periodo_fim) if competencia.tipo == "regular" else [])
        for g in o.glosas
    ]
    if glosas:
        documento.secao("Glosas do período (diário de bordo)").tabela(
            ["Data", "Registrada por", "Ocorrência", "Item", "Quantidade"], glosas, larguras=[1, 2, 5, 3, 1.2], alinhar_direita=[4],
        )
    documento.secao("Notas de Empenho (ordem de consumo)").tabela(
        ["Ordem", "Nota de Empenho", "Saldo"], [[str(o), n.numero, moeda(n.saldo)] for o, n in enumerate(notas, start=1)],
        larguras=[1, 4, 2], alinhar_direita=[2],
    )
    documento.secao("Ciências registradas").tabela(
        ["Nome", "Papel", "Ciência em"],
        [[c.nome, PAPEIS.get(c.papel, c.papel), data_hora(c.registrada_em)] for c in competencia.ciencias],
        larguras=[4, 3, 2],
    )
    return documento.gerar()


def _cnpj(valor: str | None) -> str:
    d = "".join(c for c in (valor or "") if c.isdigit())
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else (d or "não informado")


def _data_iso(valor: str | None, formato: str = "%d/%m/%Y") -> str:
    from datetime import date

    return date.fromisoformat(valor).strftime(formato) if valor else "não informada"


def _secao_nota(documento: DocumentoPdf, titulo: str, dados: dict, conferencias: list, retencoes: dict[str, Decimal], bruto: Decimal) -> None:
    """Nota renderizada a partir do XML, conferências e retenções confirmadas."""
    emitente, tomador = dados.get("emitente") or {}, dados.get("tomador") or {}
    documento.secao(titulo).campos(
        [
            ("Modelo", dados.get("modelo_rotulo") or "—"),
            ("Número / série", f"{dados.get('numero') or '—'}" + (f" / {dados['serie']}" if dados.get("serie") else "")),
            ("Emissão", _data_iso(dados.get("emissao"))),
            ("Competência", _data_iso(dados.get("competencia"), "%m/%Y")),
            ("Emitente", f"{emitente.get('razao_social') or '—'} · CNPJ {_cnpj(emitente.get('cnpj'))}"
             + (f" · IM {emitente['inscricao_municipal']}" if emitente.get("inscricao_municipal") else "")),
            ("Tomador", f"{tomador.get('razao_social') or '—'} · CNPJ {_cnpj(tomador.get('cnpj'))}"),
            ("Código do serviço", dados.get("codigo_servico") or "não informado na nota"),
            ("Situação", dados.get("situacao") or "—"),
            ("Chave", dados.get("chave") or "—"),
            ("Valor da nota (bruto)", moeda(bruto)),
        ]
    )
    itens = dados.get("itens") or []
    if itens:
        documento.tabela(
            ["Discriminação (itens)", "Qtd.", "Valor unitário", "Valor"],
            [[i.get("descricao") or "", quantidade(Decimal(i["quantidade"])) if i.get("quantidade") else "",
              f"R$ {quantidade(Decimal(i['valor_unitario']))}" if i.get("valor_unitario") else "",
              moeda(Decimal(i["valor_total"])) if i.get("valor_total") else ""]
             for i in itens],
            larguras=[6, 1, 1.6, 1.6], alinhar_direita=[1, 2, 3],
        )
    elif dados.get("discriminacao"):
        documento.paragrafo(f"Discriminação dos serviços: {dados['discriminacao']}")
    if conferencias:
        simbolo = {"ok": "Conforme", "alerta": "CONFERIR", "info": "Informativo"}
        documento.tabela(["Conferência", "Resultado", "Detalhe"], [[c.descricao, simbolo.get(c.situacao, c.situacao), c.detalhe] for c in conferencias],
                         larguras=[3, 1.4, 6])
    xml = dados.get("retencoes") or {}
    rotulos = {"ir": "IR", "inss": "INSS", "iss": "ISS", "pis": "PIS", "cofins": "COFINS", "csll": "CSLL"}
    total = sum(retencoes.values(), Decimal(0))
    documento.tabela(
        ["Tributo", "Valor no XML", "Retenção conferida"],
        [[rotulos[t], moeda(Decimal(xml.get(t) or "0")), moeda(retencoes[t])] for t in rotulos],
        larguras=[3, 2, 2], alinhar_direita=[1, 2],
        rodape=["Líquido a pagar (bruto − retenções)", f"Retenções: {moeda(total)}", moeda(bruto - total)],
    )


def relatorio_retencao(contrato: Contrato, competencia: Competencia, conferencias_principal: list, conferencias_adicional: list, autor: str) -> bytes:
    """PDF da etapa de retenção: a(s) nota(s) renderizada(s) do XML, conferências, retenções e quem conferiu."""
    documento = DocumentoPdf(
        "Retenção de tributos", f"Contrato {contrato.numero} · Competência {competencia.numero_competencia}", autor=autor,
    )
    _cabecalho_contrato(documento, contrato, competencia)
    tributos = ("ir", "inss", "iss", "pis", "cofins", "csll")
    _secao_nota(documento, "Nota fiscal (dados do XML)", competencia.nf_dados_xml or {}, conferencias_principal,
                {t: getattr(competencia, f"nf_retencao_{t}") or Decimal(0) for t in tributos}, competencia.nf_valor_bruto or Decimal(0))
    if competencia.nf_adicional_valor_bruto is not None:
        _secao_nota(documento, "Nota fiscal adicional (dados do XML)", competencia.nf_adicional_dados_xml or {}, conferencias_adicional,
                    {t: getattr(competencia, f"nf_adicional_retencao_{t}") or Decimal(0) for t in tributos}, competencia.nf_adicional_valor_bruto)
    documento.secao("Conferência").campos(
        [
            ("Conferido por", competencia.retencao_por_nome or "—"),
            ("Em", data_hora(competencia.retencao_concluida_em)),
            ("Discriminação compatível com o objeto", "Sim (confirmado)" if competencia.retencao_discriminacao_conferida else "Não confirmado"),
            ("Recebimento da NF / vencimento",
             f"{competencia.nf_recebida_em:%d/%m/%Y}" + (f" · prazo {competencia.prazo_pagamento_dias} dia(s)" if competencia.prazo_pagamento_dias else "")
             if competencia.nf_recebida_em else "—"),
        ]
    )
    return documento.gerar()


def relatorio_avaliacao(contrato: Contrato, competencia: Competencia, nota: Decimal | None, percentual: Decimal, autor: str) -> bytes:
    """PDF do relatório de avaliação: notas por grupo, resultado, ateste e linhas de assinatura."""
    avaliacao = competencia.avaliacao
    definicao = avaliacao.definicao
    iniciais = {r["item_id"]: r for r in avaliacao.respostas_iniciais or []}
    gestor = {r["item_id"]: r for r in avaliacao.respostas_gestor or []}
    # Legenda de cada nota da escala (ex.: "10" → "Ótimo")
    legendas = {str(Decimal(str(n["valor"]))): n["legenda"] for n in definicao["escala"]}
    documento = DocumentoPdf("Relatório de avaliação dos serviços", f"Contrato {contrato.numero} · Competência {competencia.competencia:%m/%Y}", autor=autor)
    _cabecalho_contrato(documento, contrato, competencia)
    # Uma tabela por grupo do formulário, com a nota inicial e a do gestor lado a lado
    for grupo in definicao["grupos"]:
        linhas = []
        for item in grupo["itens"]:
            inicial, final = iniciais.get(item["id"], {}), gestor.get(item["id"], {})
            nota_inicial = inicial.get("nota", "")
            nota_gestor = final.get("nota", "")
            linhas.append([
                item["nome"], f"{item['peso']}%",
                f"{nota_inicial} {legendas.get(str(Decimal(nota_inicial)) if nota_inicial else '', '')}".strip(),
                inicial.get("justificativa", ""),
                f"{nota_gestor} {legendas.get(str(Decimal(nota_gestor)) if nota_gestor else '', '')}".strip(),
                final.get("justificativa", ""),
            ])
        documento.secao(grupo["nome"]).tabela(
            ["Item", "Peso", "Nota inicial", "Justificativa", "Nota do gestor", "Complemento"], linhas, larguras=[3, 0.8, 1.4, 3, 1.4, 3]
        )
    documento.secao("Resultado").campos(
        [("Nota final", f"{nota}" if nota is not None else "—"), ("Pagamento liberado", f"{percentual}%"),
         ("Complemento geral do gestor", avaliacao.complemento_gestor or "—")],
        colunas=1,
    )
    # Ateste: as ciências registradas pela equipe (pessoas indicadas sem ciência, de registros antigos, ficam de fora)
    ciencias = [a for a in avaliacao.assinaturas or [] if a.get("ciencia_em")]
    documento.secao("Ateste").tabela(
        ["Papel", "Nome", "Ciência em"],
        [[PAPEIS.get(a["papel"], a["papel"]), a["nome"], str(a["ciencia_em"])[:16].replace("T", " ")] for a in ciencias],
        larguras=[2, 4, 2],
    )
    documento.assinaturas([(a["nome"], PAPEIS.get(a["papel"], a["papel"])) for a in ciencias] + [("", "Preposto da contratada")])
    return documento.gerar()


def consolidado(contrato: Contrato, competencia: Competencia, detalhe, anexos: dict, autor: str, enviados_por: dict | None = None) -> bytes:
    """Documento consolidado da competência, na ordem de execução, com páginas numeradas em sequência.

    Ordem: 1 medição (memória de cálculo) → 2 avaliação (quando houver) → 3 nota(s) fiscal(is) →
    4 retenção de tributos → 5 CADIN → 6 checklist → 7 resumo executivo (por último).
    Cada documento enviado pela equipe é precedido de uma contracapa na identidade do sistema; os
    documentos gerados pelo sistema já trazem título próprio. Os arquivos enviados entram como
    foram enviados (orientação e layout preservados), só com o selo do número da página.
    `enviados_por` traz {id do usuário: nome completo}, para a contracapa dizer quem enviou o arquivo.
    """
    enviados_por = enviados_por or {}

    def envio(anexo: Anexo | None) -> str:
        """Data e hora do envio, seguidas de "por <nome completo>" quando se sabe quem enviou."""
        if anexo is None:
            return "—"
        nome = enviados_por.get(anexo.enviado_por_id)
        return data_hora(anexo.criado_em) + (f" por {nome}" if nome else "")

    contexto = f"Contrato {contrato.numero} · Competência {competencia.competencia:%m/%Y}"

    # 1) Lista dos documentos na ordem de execução: (etapa, título, anexo_id, gerado, dados extras)
    documentos: list[tuple[str, str, object, bool, list[tuple[str, str]]]] = []
    if competencia.memorias:
        memoria = competencia.memorias[-1]
        documentos.append(("Medição", f"Memória de cálculo da medição (versão {memoria.versao})", memoria.anexo_id, True, []))
    if competencia.avaliacao:
        avaliacao = competencia.avaliacao
        # Vale a via assinada pela contratada; sem ela, o relatório gerado pelo sistema
        if avaliacao.pdf_assinado_anexo_id:
            documentos.append(("Avaliação dos serviços", "Relatório de avaliação assinado pela contratada", avaliacao.pdf_assinado_anexo_id, False, []))
        elif avaliacao.pdf_gerado_anexo_id:
            documentos.append(("Avaliação dos serviços", "Relatório de avaliação dos serviços", avaliacao.pdf_gerado_anexo_id, True, []))
    if competencia.nf_anexo_id:
        documentos.append(("Nota fiscal", f"Nota fiscal {competencia.nf_numero or ''}".strip(), competencia.nf_anexo_id, False, []))
    if competencia.nf_adicional_anexo_id:
        documentos.append(("Nota fiscal", f"Nota fiscal adicional {competencia.nf_adicional_numero or ''}".strip(),
                           competencia.nf_adicional_anexo_id, False, []))
    if competencia.retencao_pdf_anexo_id:
        documentos.append(("Avaliação de retenção", "Retenção de tributos", competencia.retencao_pdf_anexo_id, True, []))
    for consulta in competencia.consultas_cadin:
        resultado = [("Resultado", "Pendência encontrada" if consulta.possui_pendencia else "Sem pendência"),
                     ("Consulta registrada em", data_hora(consulta.criado_em)), ("Registrada por", consulta.criado_por_nome)]
        documentos.append(("CADIN", "Certidão do CADIN", consulta.certidao_anexo_id, False, resultado))
        if consulta.email_anexo_id:
            documentos.append(("CADIN", "E-mail de notificação da pendência no CADIN", consulta.email_anexo_id, False, resultado[:1]))
    for documento in competencia.documentos:
        if documento.anexo_id:
            tipo = "Obrigatório" if documento.obrigatorio else "Opcional"
            extras = [("Item do checklist", f"{documento.ordem} · {tipo}")] + ([("Observação", documento.observacao)] if documento.observacao else [])
            documentos.append(("Checklist", documento.nome, documento.anexo_id, False, extras))

    # 2) Monta as partes: contracapa (para os enviados) + o arquivo; anota as páginas de cada um
    partes: list[tuple[bytes | object, bool]] = []
    composicao: list[list[str]] = []
    pagina = 1
    total_documentos = len(documentos) + 1  # + o resumo executivo, ao final
    for posicao, (etapa, titulo, anexo_id, gerado, extras) in enumerate(documentos, start=1):
        anexo: Anexo | None = anexos.get(anexo_id) if anexo_id else None
        caminho = servico_anexos.caminho(anexo) if anexo else None
        legivel = bool(caminho and caminho.is_file() and _pdf_legivel(caminho.read_bytes()))
        inicio = pagina
        if not gerado or not legivel:
            dados = [("Etapa", etapa), ("Arquivo", anexo.nome_original if anexo else "—"),
                     ("Enviado em" if not gerado else "Gerado em", envio(anexo)), *extras]
            if not legivel:
                dados.append(("Situação", "Arquivo ausente ou ilegível: não foi incluído neste consolidado."))
            capa = contracapa(f"Documento {posicao} de {total_documentos} · {etapa}", titulo, dados, contexto, autor)
            partes.append((capa, True))
            pagina += contar_paginas(capa)
        if legivel:
            partes.append((caminho, gerado))
            pagina += contar_paginas(caminho)
        composicao.append([str(posicao), etapa, titulo, f"{inicio}" if pagina - 1 == inicio else f"{inicio} a {pagina - 1}"])

    # 3) Resumo executivo, por último: dados da competência e a composição do documento
    resumo = DocumentoPdf("Resumo executivo da competência", contexto, autor=autor)
    _cabecalho_contrato(resumo, contrato, competencia)
    resumo.secao("Resumo executivo").campos(
        [
            ("Total previsto", moeda(detalhe.total_previsto)),
            ("Total medido", moeda(detalhe.total_medido)),
            ("% autorizado pela avaliação", f"{detalhe.percentual_autorizado}%"),
            ("Valor autorizado", moeda(detalhe.valor_autorizado)),
            ("Nota fiscal", detalhe.nota_fiscal.numero if detalhe.nota_fiscal else "—"),
            ("Valor líquido da NF", moeda(detalhe.nota_fiscal.valor_liquido) if detalhe.nota_fiscal else "—"),
            ("NF adicional", detalhe.nota_fiscal_adicional.numero if detalhe.nota_fiscal_adicional else "—"),
            ("Vencimento do pagamento", f"{detalhe.vencimento_pagamento:%d/%m/%Y}" if detalhe.vencimento_pagamento else "—"),
            ("Notas de Empenho", ", ".join(n.numero for n in detalhe.notas_selecionadas) or "—"),
            ("Avaliação (nota final)", f"{detalhe.avaliacao.nota_final}" if detalhe.avaliacao and detalhe.avaliacao.nota_final is not None else "Sem avaliação"),
        ]
    )
    resumo.secao("Histórico do CADIN").tabela(
        ["Data", "Resultado", "Pendência", "Registrado por"],
        [[data_hora(c.criado_em), "Pendência encontrada" if c.possui_pendencia else "Sem pendência", c.pendencia or "—", c.criado_por_nome]
         for c in detalhe.consultas_cadin],
        larguras=[1.6, 2, 4, 2.4],
    )
    resumo.secao("Checklist mensal").tabela(
        ["Nº", "Documento", "Tipo", "Arquivo"],
        [[str(d.ordem), d.nome, "Obrigatório" if d.obrigatorio else "Opcional", d.arquivo.nome if d.arquivo else "Não anexado"] for d in detalhe.documentos],
        larguras=[0.5, 4, 1.4, 3.6]
    )
    composicao.append([str(total_documentos), "Resumo executivo", "Resumo executivo da competência", f"a partir da {pagina}"])
    resumo.secao("Composição deste documento").tabela(["Nº", "Etapa", "Documento", "Páginas"], composicao, larguras=[0.5, 2, 5, 1.5])
    partes.append((resumo.gerar(), True))
    return montar_consolidado(partes)


def _pdf_legivel(conteudo: bytes) -> bool:
    """Um PDF corrompido não pode impedir o consolidado: ele fica de fora e o resumo lista o anexo."""
    try:
        PdfReader(BytesIO(conteudo))
        return True
    except Exception:  # noqa: BLE001 — qualquer falha de leitura do PDF enviado
        return False
