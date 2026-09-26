# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras do diário de bordo do contrato: registro, glosas e PDF.
"""Diário de bordo do contrato.

A equipe (criador, integrantes vigentes ou SuperRoot) relata ocorrências da execução. Uma ocorrência
pode implicar glosa de itens do contrato; as glosas valem na competência cujo período contém a data da
ocorrência e limitam o que pode ser medido nela. As ocorrências não são editadas nem excluídas.
"""

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratos import Competencia, Contrato, GlosaOcorrencia, OcorrenciaDiario
from app.models.usuario import Usuario
from app.schemas.contratos.diario import (
    DiarioContrato,
    EnvioEmail,
    GravacaoOcorrencia,
    LeituraGlosa,
    LeituraOcorrencia,
    OpcaoItemGlosa,
)
from app.services.contratos.documentos_execucao import PAPEIS, data_hora, quantidade
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_contratos import designacoes_vigentes, exigir_edicao, hoje, obter_contrato, pode_editar
from app.services.documentos.pdf import DocumentoPdf
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)


def competencia_da_data(contrato: Contrato, dia: date) -> Competencia | None:
    """Competência regular cujo período contém o dia (onde as glosas daquela data valem)."""
    return next((c for c in contrato.competencias if c.tipo == "regular" and c.periodo_inicio <= dia <= c.periodo_fim), None)


def ocorrencias_do_periodo(contrato: Contrato, inicio: date | None, fim: date | None) -> list[OcorrenciaDiario]:
    """Ocorrências com data dentro do período (limites inclusivos; vazio = sem limite)."""
    return sorted(
        (o for o in contrato.ocorrencias if (inicio is None or o.data_ocorrencia >= inicio) and (fim is None or o.data_ocorrencia <= fim)),
        key=lambda o: (o.data_ocorrencia, o.criado_em),
    )


def glosas_do_periodo(contrato: Contrato, inicio: date, fim: date) -> dict[uuid.UUID, Decimal]:
    """Quantidade glosada por item nas ocorrências com data dentro do período."""
    total: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for ocorrencia in ocorrencias_do_periodo(contrato, inicio, fim):
        for glosa in ocorrencia.glosas:
            total[glosa.item_id] += glosa.quantidade
    return dict(total)


def _papel(contrato: Contrato, autor: Usuario) -> str:
    """Papel de quem registra: o da designação vigente, ou vazio (criador/SuperRoot fora da equipe)."""
    return next((d.papel for d in designacoes_vigentes(contrato) if d.usuario_id == autor.id), "")


def registrar(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoOcorrencia, autor: Usuario) -> OcorrenciaDiario:
    """Registra a ocorrência (e as glosas). O e-mail à equipe e ao preposto é enviado depois, em segundo plano."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    if dados.data_ocorrencia > hoje():
        raise ErroRegraContrato("A data da ocorrência não pode ser futura.")
    if dados.data_ocorrencia < contrato.data_inicio:
        raise ErroRegraContrato(f"A data da ocorrência é anterior ao início do contrato ({contrato.data_inicio:%d/%m/%Y}).")
    itens = {i.id: i for i in contrato.itens}
    for glosa in dados.glosas:
        if glosa.item_id not in itens:
            raise ErroRegraContrato("A glosa aponta para um item que não é deste contrato.")
    ocorrencia = OcorrenciaDiario(
        data_ocorrencia=dados.data_ocorrencia, descricao=dados.descricao, possui_glosa=dados.possui_glosa,
        registrada_por_id=autor.id, registrada_por_nome=autor.nome_completo or autor.login, registrada_por_papel=_papel(contrato, autor),
        criado_em=agora_utc(),
        glosas=[GlosaOcorrencia(item_id=g.item_id, descricao_item=itens[g.item_id].descricao, quantidade=g.quantidade) for g in dados.glosas],
    )
    contrato.ocorrencias.append(ocorrencia)
    sessao.flush()
    auditar(
        sessao, autor.login, "contrato.diario.registrar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
        alvo_id=contrato.id,
        dados={"ocorrencia": ocorrencia.id, "data": dados.data_ocorrencia, "glosas": [{"item": str(g.item_id), "quantidade": g.quantidade} for g in dados.glosas]},
    )
    sessao.commit()
    return ocorrencia


def obter_ocorrencia(contrato: Contrato, ocorrencia_id: uuid.UUID) -> OcorrenciaDiario:
    """Ocorrência do contrato pelo id, ou 404."""
    ocorrencia = next((o for o in contrato.ocorrencias if o.id == ocorrencia_id), None)
    if ocorrencia is None:
        raise RegistroNaoEncontrado("Ocorrência")
    return ocorrencia


def leitura(contrato: Contrato, ocorrencia: OcorrenciaDiario) -> LeituraOcorrencia:
    """Ocorrência no formato da API, com a competência da data e o estado do e-mail."""
    competencia = competencia_da_data(contrato, ocorrencia.data_ocorrencia)
    return LeituraOcorrencia(
        id=ocorrencia.id, data_ocorrencia=ocorrencia.data_ocorrencia, descricao=ocorrencia.descricao, possui_glosa=ocorrencia.possui_glosa,
        glosas=[LeituraGlosa(item_id=g.item_id, descricao_item=g.descricao_item, quantidade=g.quantidade) for g in ocorrencia.glosas],
        registrada_por_id=ocorrencia.registrada_por_id, registrada_por_nome=ocorrencia.registrada_por_nome,
        registrada_por_papel=ocorrencia.registrada_por_papel, criado_em=ocorrencia.criado_em,
        competencia_rotulo=competencia.numero_competencia if competencia else None,
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
    )


def gerar_pdf(contrato: Contrato, inicio: date | None = None, fim: date | None = None, autor: str = "") -> bytes:
    """Diário de bordo em PDF (A4 paisagem, mesmo padrão da memória de cálculo)."""
    periodo = (
        f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}" if inicio and fim
        else f"desde {inicio:%d/%m/%Y}" if inicio else f"até {fim:%d/%m/%Y}" if fim else "todo o contrato"
    )
    documento = DocumentoPdf("Diário de bordo", f"Contrato {contrato.numero} · {periodo}", paisagem=True, autor=autor)
    documento.secao("Identificação").campos(
        [
            ("Contrato", contrato.numero),
            ("Período", periodo),
            ("Contratada", contrato.empresa.razao_social),
            ("Processo SEI (execução)", contrato.sei_execucao_numero),
            ("Objeto", contrato.objeto),
        ]
    )
    ocorrencias = ocorrencias_do_periodo(contrato, inicio, fim)
    linhas = [
        [
            f"{o.data_ocorrencia:%d/%m/%Y}",
            f"{o.registrada_por_nome}" + (f" ({PAPEIS.get(o.registrada_por_papel, o.registrada_por_papel)})" if o.registrada_por_papel else "")
            + f"\n{data_hora(o.criado_em)}",
            o.descricao,
            "; ".join(f"{g.descricao_item}: {quantidade(g.quantidade)}" for g in o.glosas) if o.possui_glosa else "Não",
        ]
        for o in ocorrencias
    ]
    documento.secao(f"Ocorrências ({len(ocorrencias)})")
    if linhas:
        documento.tabela(["Data", "Registrada por / em", "Ocorrência", "Glosa"], linhas, larguras=[1.2, 2.6, 6.2, 3])
    else:
        documento.paragrafo("Nenhuma ocorrência registrada no período.")
    # Totais por item, para conferência com a medição
    totais: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for o in ocorrencias:
        for g in o.glosas:
            totais[g.descricao_item] += g.quantidade
    if totais:
        documento.secao("Glosas por item").tabela(
            ["Item", "Quantidade glosada"], [[item, quantidade(q)] for item, q in sorted(totais.items())], larguras=[8, 2], alinhar_direita=[1]
        )
    return documento.gerar()
