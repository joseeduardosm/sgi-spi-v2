"""PDFs da execução: memória de cálculo da medição, relatório de avaliação e documento consolidado."""

from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader

from app.models.anexo import Anexo
from app.models.contratos import Competencia, Contrato, NotaEmpenho
from app.services import servico_anexos
from app.services.contratos.calculos import arredondar
from app.services.documentos.pdf import FUSO_SAO_PAULO, DocumentoPdf, mesclar_pdfs

PAPEIS = {
    "gestor": "Gestor",
    "gestor_suplente": "Suplente do gestor",
    "fiscal_administrativo": "Fiscal administrativo",
    "fiscal_administrativo_suplente": "Suplente administrativo",
    "fiscal_tecnico": "Fiscal técnico",
    "fiscal_tecnico_suplente": "Suplente técnico",
}


def moeda(valor: Decimal | None) -> str:
    if valor is None:
        return "R$ -"
    texto = f"{arredondar(Decimal(valor)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def quantidade(valor: Decimal) -> str:
    """Até 4 casas, sem zeros à direita, no formato brasileiro (ex.: 1.234,5)."""
    texto = f"{Decimal(valor):,.4f}".rstrip("0").rstrip(".")
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def data_hora(valor) -> str:
    return valor.astimezone(FUSO_SAO_PAULO).strftime("%d/%m/%Y %H:%M") if valor else "—"


def _cabecalho_contrato(documento: DocumentoPdf, contrato: Contrato, competencia: Competencia) -> None:
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
    documento = DocumentoPdf(
        "Memória de cálculo da medição", f"Contrato {contrato.numero} · Competência {competencia.competencia:%m/%Y} · versão {versao}",
        paisagem=True, autor=autor,
    )
    _cabecalho_contrato(documento, contrato, competencia)
    total = Decimal(0)
    linhas = []
    for item in competencia.itens:
        subtotal = arredondar(item.quantidade_medida * item.valor_unitario)
        total += subtotal
        linhas.append(
            [str(item.ordem), item.descricao, "Contínuo" if item.tipo == "continuo" else "Sob demanda", moeda(item.valor_unitario),
             quantidade(item.quantidade_prevista), quantidade(item.quantidade_medida), moeda(subtotal)]
        )
    documento.secao("Medição do serviço").tabela(
        ["Item", "Descrição", "Tipo", "Valor unitário", "Qtd. prevista", "Medição", "Subtotal"], linhas,
        larguras=[0.5, 5, 1.3, 1.5, 1.3, 1.3, 1.6], alinhar_direita=[3, 4, 5, 6], rodape=["", "Total medido", "", "", "", "", moeda(total)],
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


def relatorio_avaliacao(contrato: Contrato, competencia: Competencia, nota: Decimal | None, percentual: Decimal, autor: str) -> bytes:
    avaliacao = competencia.avaliacao
    definicao = avaliacao.definicao
    iniciais = {r["item_id"]: r for r in avaliacao.respostas_iniciais or []}
    gestor = {r["item_id"]: r for r in avaliacao.respostas_gestor or []}
    legendas = {str(Decimal(str(n["valor"]))): n["legenda"] for n in definicao["escala"]}
    documento = DocumentoPdf("Relatório de avaliação dos serviços", f"Contrato {contrato.numero} · Competência {competencia.competencia:%m/%Y}", autor=autor)
    _cabecalho_contrato(documento, contrato, competencia)
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
    documento.secao("Ateste").tabela(
        ["Papel", "Nome", "Ciência em"],
        [[PAPEIS.get(a["papel"], a["papel"]), a["nome"], (a.get("ciencia_em") or "—")[:16].replace("T", " ")] for a in avaliacao.assinaturas or []],
        larguras=[2, 4, 2],
    )
    documento.assinaturas([(a["nome"], PAPEIS.get(a["papel"], a["papel"])) for a in avaliacao.assinaturas or []] + [("", "Preposto da contratada")])
    return documento.gerar()


def consolidado(contrato: Contrato, competencia: Competencia, detalhe, anexos: dict, autor: str) -> bytes:
    """Resumo executivo seguido de todos os PDFs da competência, na ordem das etapas."""
    resumo = DocumentoPdf("Documento consolidado da competência", f"Contrato {contrato.numero} · Competência {competencia.competencia:%m/%Y}", autor=autor)
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
    partes: list[bytes | object] = [resumo.gerar()]
    ordem = []
    if competencia.memorias:
        ordem.append(competencia.memorias[-1].anexo_id)
    if competencia.avaliacao:
        ordem.append(competencia.avaliacao.pdf_assinado_anexo_id)
    ordem += [competencia.nf_anexo_id, competencia.nf_adicional_anexo_id]
    for consulta in competencia.consultas_cadin:
        ordem += [consulta.certidao_anexo_id, consulta.email_anexo_id]
    ordem += [d.anexo_id for d in competencia.documentos]
    for anexo_id in ordem:
        anexo: Anexo | None = anexos.get(anexo_id) if anexo_id else None
        if anexo is None:
            continue
        caminho = servico_anexos.caminho(anexo)
        if caminho.is_file() and _pdf_legivel(caminho.read_bytes()):
            partes.append(caminho)
    return mesclar_pdfs(partes)


def _pdf_legivel(conteudo: bytes) -> bool:
    """Um PDF corrompido não pode impedir o consolidado: ele fica de fora e o resumo lista o anexo."""
    try:
        PdfReader(BytesIO(conteudo))
        return True
    except Exception:  # noqa: BLE001 — qualquer falha de leitura do PDF enviado
        return False
