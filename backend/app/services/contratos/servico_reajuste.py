# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de reajuste de preços, memória e apostilamento.
"""Reajuste de preços (tela 6): abertura, evidência do índice, memória, apostilamento e conclusão.

Regras: um reajuste em elaboração por vez; cada vigência é reajustada uma vez. Competências já
medidas mantêm os preços antigos (princípio da fotografia).
"""

import hashlib
import json
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.anexo import Anexo
from app.models.contratos import Competencia, Contrato, ItemMedicao, ItemReajuste, MemoriaReajuste, Reajuste
from app.models.usuario import Usuario
from app.schemas.contratos.alteracoes import (
    AberturaReajuste,
    GravacaoMemoriaReajuste,
    ItemReajusteLeitura,
    LeituraMemoriaVersao,
    LeituraReajuste,
    PainelReajuste,
    VigenciaDisponivel,
)
from app.schemas.contratos.execucao import LeituraArquivo
from app.services import servico_anexos
from app.services.contratos import calculos, valores
from app.services.contratos.documentos_execucao import moeda, quantidade
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_configuracao_execucao import checklist_ativo, copiar_checklist
from app.services.contratos.servico_contratos import exigir_edicao, obter_contrato, pode_editar, vigencias
from app.services.documentos.pdf import DocumentoPdf
from app.services.documentos.planilha import FORMATO_MOEDA, FORMATO_QUANTIDADE, Aba, Coluna, gerar_planilha
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)
CEM = Decimal(100)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _arquivo(anexo: Anexo | None) -> LeituraArquivo | None:
    return LeituraArquivo(anexo_id=anexo.id, nome=anexo.nome_original, tamanho=anexo.tamanho, enviado_em=anexo.criado_em) if anexo else None


def _carregar(sessao: Session, contrato: Contrato) -> list[Reajuste]:
    return list(
        sessao.scalars(
            select(Reajuste)
            .where(Reajuste.contrato_id == contrato.id)
            .options(selectinload(Reajuste.itens), selectinload(Reajuste.memorias).selectinload(MemoriaReajuste.pdf_anexo),
                     selectinload(Reajuste.memorias).selectinload(MemoriaReajuste.xlsx_anexo))
            .order_by(Reajuste.criado_em)
        )
    )


def _vigencia(contrato: Contrato, sequencia: int) -> calculos.Vigencia:
    vigencia = next((v for v in vigencias(contrato) if v.sequencia == sequencia), None)
    if vigencia is None:
        raise RegistroNaoEncontrado("Vigência")
    return vigencia


def calcular_totais(contrato: Contrato, reajuste: Reajuste) -> None:
    """Bases mensais e valores globais da vigência, antes e depois do reajuste.

    O valor global usa o mesmo cálculo mês a mês do contrato (`valores.valor_global_vigencia`): os novos
    preços valem a partir do mês de referência, inclusive nos meses já medidos, cuja diferença é paga
    por uma competência complementar ao concluir o reajuste.
    """
    vigencia = _vigencia(contrato, reajuste.sequencia_vigencia)
    base_atual = base_nova = ZERO
    for linha in reajuste.itens:
        if linha.tipo == "continuo":
            base_atual += linha.quantidade_mensal * linha.valor_unitario_atual
            base_nova += linha.quantidade_mensal * linha.valor_unitario_reajustado
    novos = {linha.item_id: linha.valor_unitario_reajustado for linha in reajuste.itens}
    atual = valores.valor_global_vigencia(contrato, vigencia)
    reajuste.base_atual, reajuste.base_reajustada = calculos.arredondar(base_atual), calculos.arredondar(base_nova)
    reajuste.valor_global_atual = atual
    reajuste.valor_global_reajustado = valores.valor_global_vigencia(contrato, vigencia, (reajuste.mes_referencia, novos))


def _competencias_afetadas(contrato: Contrato, reajuste: Reajuste) -> list[Competencia]:
    """Competências regulares ainda não medidas a partir da referência: recebem o novo preço."""
    return [
        c for c in contrato.competencias
        if c.tipo == "regular" and c.sequencia_vigencia == reajuste.sequencia_vigencia
        and c.competencia >= reajuste.mes_referencia and c.medicao_concluida_em is None
    ]


def _competencias_medidas(contrato: Contrato, reajuste: Reajuste) -> list[Competencia]:
    """Competências regulares já medidas a partir da referência: a diferença de preço delas é paga à parte."""
    return sorted(
        (
            c for c in contrato.competencias
            if c.tipo == "regular" and c.sequencia_vigencia == reajuste.sequencia_vigencia
            and c.competencia >= reajuste.mes_referencia and c.medicao_concluida_em is not None
        ),
        key=lambda c: c.periodo_inicio,
    )


def gerar_competencia_diferenca(contrato: Contrato, reajuste: Reajuste, novos: dict) -> Competencia | None:
    """Competência complementar (`diferenca_reajuste`) com a diferença de preço das quantidades já medidas.

    Por item: quantidade = soma das medições concluídas desde a referência; valor unitário = preço
    reajustado − preço fotografado na competência (média ponderada, se houver preços diferentes).
    A medição já vem preenchida e segue o fluxo normal: NEs e ciências, nota fiscal, CADIN,
    checklist, consolidado e Ordem Bancária (sem avaliação).
    """
    medidas = _competencias_medidas(contrato, reajuste)
    quantidades: dict = {}
    valores_diferenca: dict = {}
    for competencia in medidas:
        for linha in competencia.itens:
            if linha.item_id not in novos or linha.quantidade_medida <= 0:
                continue
            quantidades[linha.item_id] = quantidades.get(linha.item_id, ZERO) + linha.quantidade_medida
            valores_diferenca[linha.item_id] = valores_diferenca.get(linha.item_id, ZERO) + linha.quantidade_medida * (
                novos[linha.item_id] - linha.valor_unitario
            )
    if not quantidades or calculos.arredondar(sum(valores_diferenca.values(), ZERO)) == 0:
        return None
    itens = {i.id: i for i in contrato.itens}
    competencia = Competencia(
        tipo="diferenca_reajuste", reajuste_id=reajuste.id, competencia=reajuste.mes_referencia,
        periodo_inicio=medidas[0].periodo_inicio, periodo_fim=medidas[-1].periodo_fim,
        sequencia_vigencia=reajuste.sequencia_vigencia, etapa_atual="medicao",
    )
    for item_id, total_medido in quantidades.items():
        item = itens[item_id]
        unitario = calculos.arredondar(valores_diferenca[item_id] / total_medido)
        competencia.itens.append(
            ItemMedicao(
                item_id=item_id, ordem=item.ordem, descricao=f"{item.descricao} (diferença de reajuste)", tipo=item.tipo,
                calcula_pro_rata=item.calcula_pro_rata, valor_unitario=unitario, fator_meses=Decimal(len(medidas)),
                quantidade_prevista=total_medido, quantidade_medida=total_medido,
            )
        )
    checklist = checklist_ativo(contrato)
    if checklist:
        copiar_checklist(competencia, checklist)
    contrato.competencias.append(competencia)
    return competencia


def leitura(contrato: Contrato, reajuste: Reajuste, anexos: dict) -> LeituraReajuste:
    return LeituraReajuste(
        id=reajuste.id, situacao=reajuste.situacao, sequencia_vigencia=reajuste.sequencia_vigencia, vigencia_inicio=reajuste.vigencia_inicio,
        vigencia_fim=reajuste.vigencia_fim, mes_referencia=reajuste.mes_referencia,
        competencias_recalculadas=len(_competencias_afetadas(contrato, reajuste)) if reajuste.situacao == "rascunho" else 0,
        competencias_com_diferenca=len(_competencias_medidas(contrato, reajuste)) if reajuste.situacao == "rascunho" else 0,
        competencia_diferenca=next(
            (c.identificador for c in contrato.competencias if c.tipo == "diferenca_reajuste" and c.reajuste_id == reajuste.id), None
        ),
        itens=[
            ItemReajusteLeitura(
                item_id=i.item_id, ordem=i.ordem, descricao=i.descricao, tipo=i.tipo, quantidade_mensal=i.quantidade_mensal,
                valor_unitario_atual=i.valor_unitario_atual, indice_percentual=i.indice_percentual, valor_referencial=i.valor_referencial,
                valor_unitario_reajustado=i.valor_unitario_reajustado,
                subtotal_reajustado=calculos.arredondar(i.quantidade_mensal * i.valor_unitario_reajustado),
            )
            for i in reajuste.itens
        ],
        base_atual=reajuste.base_atual, base_reajustada=reajuste.base_reajustada, valor_global_atual=reajuste.valor_global_atual,
        valor_global_reajustado=reajuste.valor_global_reajustado, evidencia=_arquivo(anexos.get(reajuste.evidencia_anexo_id)),
        apostilamento=_arquivo(anexos.get(reajuste.apostilamento_anexo_id)),
        memorias=[LeituraMemoriaVersao(versao=m.versao, criada_em=m.criado_em, pdf=_arquivo(m.pdf_anexo), xlsx=_arquivo(m.xlsx_anexo)) for m in reajuste.memorias],
        concluido_em=reajuste.concluido_em, cancelado_em=reajuste.cancelado_em,
    )


def painel(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> PainelReajuste:
    contrato = obter_contrato(sessao, contrato_id)
    reajustes = _carregar(sessao, contrato)
    ids = [x for r in reajustes for x in (r.evidencia_anexo_id, r.apostilamento_anexo_id) if x]
    anexos = {a.id: a for a in sessao.scalars(select(Anexo).where(Anexo.id.in_(ids)))}
    reajustadas = {r.sequencia_vigencia for r in reajustes if r.situacao == "concluido"}
    em_andamento = next((r for r in reajustes if r.situacao == "rascunho"), None)
    return PainelReajuste(
        em_andamento=leitura(contrato, em_andamento, anexos) if em_andamento else None,
        vigencias_disponiveis=[VigenciaDisponivel(sequencia=v.sequencia, inicio=v.inicio, fim=v.fim) for v in vigencias(contrato) if v.sequencia not in reajustadas],
        historico=[leitura(contrato, r, anexos) for r in reajustes if r.situacao != "rascunho"],
        pode_editar=pode_editar(sessao, contrato, usuario),
    )


def _em_andamento(sessao: Session, contrato: Contrato, reajuste_id: uuid.UUID) -> Reajuste:
    reajuste = next((r for r in _carregar(sessao, contrato) if r.id == reajuste_id), None)
    if reajuste is None:
        raise RegistroNaoEncontrado("Reajuste")
    if reajuste.situacao != "rascunho":
        raise ErroRegraContrato("Este reajuste não está mais em elaboração.")
    return reajuste


def abrir(sessao: Session, contrato_id: uuid.UUID, dados: AberturaReajuste, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    existentes = _carregar(sessao, contrato)
    if any(r.situacao == "rascunho" for r in existentes):
        raise ErroRegraContrato("Já existe um reajuste em elaboração. Conclua ou cancele-o antes.", conflito=True)
    if any(r.situacao == "concluido" and r.sequencia_vigencia == dados.sequencia_vigencia for r in existentes):
        raise ErroRegraContrato("Esta vigência já foi reajustada.")
    vigencia = _vigencia(contrato, dados.sequencia_vigencia)
    referencia = calculos.primeiro_dia(dados.mes_referencia)
    if not calculos.primeiro_dia(vigencia.inicio) <= referencia <= vigencia.fim:
        raise ErroRegraContrato("O mês de referência precisa estar dentro da vigência escolhida.")
    reajuste = Reajuste(
        contrato_id=contrato.id, sequencia_vigencia=vigencia.sequencia, vigencia_inicio=vigencia.inicio, vigencia_fim=vigencia.fim,
        mes_referencia=referencia, criado_por_id=autor.id,
    )
    for item in contrato.itens:
        preco = valores.preco_em(contrato, item, referencia)
        reajuste.itens.append(
            ItemReajuste(
                item_id=item.id, ordem=item.ordem, descricao=item.descricao, tipo=item.tipo,
                quantidade_mensal=valores.quantidade_mensal_em(contrato, item, referencia), valor_unitario_atual=preco,
                indice_percentual=ZERO, valor_unitario_reajustado=preco,
            )
        )
    sessao.add(reajuste)
    calcular_totais(contrato, reajuste)
    auditar(sessao, autor.login, "contrato.reajuste.abrir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"vigencia": vigencia.sequencia, "mes_referencia": referencia})
    sessao.commit()


def anexar_evidencia(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-reajuste-evidencia", autor.id, contrato_id=contrato.id)
    sessao.flush()
    reajuste.evidencia_anexo_id = anexo.id
    auditar(sessao, autor.login, "contrato.reajuste.evidencia", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
    sessao.commit()


def reajustar_preco(atual: Decimal, indice: Decimal, referencial: Decimal | None) -> Decimal:
    """Preço × (1 + índice/100), com 2 casas; o valor referencial, quando informado, é o teto."""
    novo = (atual * (1 + indice / CEM)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return min(novo, referencial) if referencial is not None else novo


def salvar_memoria(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, dados: GravacaoMemoriaReajuste, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    linhas = {i.item_id: i for i in reajuste.itens}
    if {i.item_id for i in dados.itens} - set(linhas):
        raise ErroRegraContrato("Um dos itens não pertence a este reajuste.")
    for entrada in dados.itens:
        linha = linhas[entrada.item_id]
        linha.indice_percentual, linha.valor_referencial = entrada.indice_percentual, entrada.valor_referencial
        linha.valor_unitario_reajustado = reajustar_preco(linha.valor_unitario_atual, entrada.indice_percentual, entrada.valor_referencial)
    calcular_totais(contrato, reajuste)
    auditar(sessao, autor.login, "contrato.reajuste.memoria", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"itens": {str(i.item_id): {"indice": i.indice_percentual, "novo": i.valor_unitario_reajustado} for i in reajuste.itens}})
    sessao.commit()


def gerar_arquivos_memoria(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, autor: Usuario) -> None:
    """PDF e XLSX da memória; nova versão só se os dados mudaram."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    origem = hashlib.sha256(json.dumps(
        [[str(i.item_id), str(i.valor_unitario_atual), str(i.indice_percentual), str(i.valor_referencial), str(i.valor_unitario_reajustado)] for i in reajuste.itens]
        + [str(reajuste.mes_referencia)]
    ).encode()).hexdigest()
    if reajuste.memorias and reajuste.memorias[-1].hash_origem == origem:
        return
    versao = len(reajuste.memorias) + 1
    base = f"memoria-reajuste-{contrato.sequencial:03d}-{contrato.ano}-v{versao}"
    pdf = servico_anexos.guardar_pdf_gerado(sessao, _pdf_memoria(contrato, reajuste, versao, autor), f"{base}.pdf", "contrato-reajuste-memoria", autor.id, contrato_id=contrato.id)
    xlsx = servico_anexos.guardar_arquivo_gerado(sessao, _xlsx_memoria(contrato, reajuste), f"{base}.xlsx", XLSX, "contrato-reajuste-memoria", autor.id, contrato_id=contrato.id)
    reajuste.memorias.append(MemoriaReajuste(versao=versao, pdf_anexo=pdf, xlsx_anexo=xlsx, hash_origem=origem, criado_por_id=autor.id, criado_em=agora_utc()))
    auditar(sessao, autor.login, "contrato.reajuste.memoria.gerar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"versao": versao})
    sessao.commit()


def _linhas(reajuste: Reajuste) -> list[list]:
    return [
        [i.ordem, i.descricao, i.quantidade_mensal, i.valor_unitario_atual, i.indice_percentual, i.valor_referencial, i.valor_unitario_reajustado,
         calculos.arredondar(i.quantidade_mensal * i.valor_unitario_reajustado)]
        for i in reajuste.itens
    ]


def _pdf_memoria(contrato: Contrato, reajuste: Reajuste, versao: int, autor: Usuario) -> bytes:
    documento = DocumentoPdf("Memória de cálculo do reajuste", f"Contrato {contrato.numero} · {reajuste.sequencia_vigencia}ª vigência · versão {versao}",
                             paisagem=True, autor=autor.nome_completo or autor.login)
    documento.secao("Identificação").campos([
        ("Contrato", contrato.numero), ("Contratada", contrato.empresa.razao_social),
        ("Vigência", f"{reajuste.vigencia_inicio:%d/%m/%Y} a {reajuste.vigencia_fim:%d/%m/%Y}"), ("Mês de referência", f"{reajuste.mes_referencia:%m/%Y}"),
    ])
    documento.secao("Itens").tabela(
        ["Item", "Descrição", "Qtd. mensal", "Valor atual", "Índice (%)", "Referencial", "Valor reajustado", "Subtotal reajustado"],
        [[str(l[0]), l[1], quantidade(l[2]), moeda(l[3]), f"{l[4]:.4f}".replace(".", ","), moeda(l[5]) if l[5] is not None else "—", moeda(l[6]), moeda(l[7])]
         for l in _linhas(reajuste)],
        larguras=[0.5, 4, 1.2, 1.4, 1.1, 1.4, 1.5, 1.6], alinhar_direita=[2, 3, 4, 5, 6, 7],
    )
    documento.secao("Totais").campos([
        ("Base atual", moeda(reajuste.base_atual)), ("Nova base por competência", moeda(reajuste.base_reajustada)),
        ("Valor global atual", moeda(reajuste.valor_global_atual)), ("Novo valor global", moeda(reajuste.valor_global_reajustado)),
    ])
    return documento.gerar()


def _xlsx_memoria(contrato: Contrato, reajuste: Reajuste) -> bytes:
    return gerar_planilha([Aba(
        "Reajuste",
        [Coluna("Item", largura=6), Coluna("Descrição", largura=40), Coluna("Qtd. mensal", FORMATO_QUANTIDADE), Coluna("Valor atual", FORMATO_MOEDA),
         Coluna("Índice (%)", "0.0000"), Coluna("Referencial", FORMATO_MOEDA), Coluna("Valor reajustado", FORMATO_MOEDA), Coluna("Subtotal reajustado", FORMATO_MOEDA, 20)],
        _linhas(reajuste),
        titulo=f"Memória de cálculo do reajuste — Contrato {contrato.numero} — referência {reajuste.mes_referencia:%m/%Y}",
        observacoes=[f"Base atual: {moeda(reajuste.base_atual)} · Nova base: {moeda(reajuste.base_reajustada)}",
                     f"Valor global atual: {moeda(reajuste.valor_global_atual)} · Novo valor global: {moeda(reajuste.valor_global_reajustado)}"],
    )])


def concluir(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Anexa o apostilamento e aplica os preços: itens, competências ainda não medidas e valor global."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    if reajuste.evidencia_anexo_id is None:
        raise ErroRegraContrato("Anexe a evidência do índice antes de concluir.")
    if not reajuste.memorias:
        raise ErroRegraContrato("Gere a memória de cálculo (PDF/XLSX) antes de concluir.")
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-reajuste-apostilamento", autor.id, contrato_id=contrato.id)
    sessao.flush()
    reajuste.apostilamento_anexo_id = anexo.id
    novos = {i.item_id: i.valor_unitario_reajustado for i in reajuste.itens}
    ultima_vigencia = vigencias(contrato)[-1].sequencia
    for item in contrato.itens:
        if item.id in novos and reajuste.sequencia_vigencia == ultima_vigencia:
            item.valor_unitario = novos[item.id]
    afetadas = _competencias_afetadas(contrato, reajuste)
    for competencia in afetadas:
        for linha in competencia.itens:
            if linha.item_id in novos:
                linha.valor_unitario = novos[linha.item_id]
    if reajuste.sequencia_vigencia == ultima_vigencia:
        contrato.valor_global_reajustado = reajuste.valor_global_reajustado
    diferenca = gerar_competencia_diferenca(contrato, reajuste, novos)
    reajuste.situacao, reajuste.concluido_em = "concluido", agora_utc()
    contrato.versao += 1
    auditar(sessao, autor.login, "contrato.reajuste.concluir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"mes_referencia": reajuste.mes_referencia, "competencias_recalculadas": len(afetadas),
                   "competencia_diferenca": diferenca.identificador if diferenca else None,
                   "campos": {"valor_global": {"de": reajuste.valor_global_atual, "para": reajuste.valor_global_reajustado}}})
    sessao.commit()


def cancelar(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    reajuste.situacao, reajuste.cancelado_em = "cancelado", agora_utc()
    auditar(sessao, autor.login, "contrato.reajuste.cancelar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
    sessao.commit()


def arquivo(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, anexo_id: uuid.UUID):
    contrato = obter_contrato(sessao, contrato_id)
    reajuste = next((r for r in _carregar(sessao, contrato) if r.id == reajuste_id), None)
    if reajuste is None:
        raise RegistroNaoEncontrado("Reajuste")
    permitidos = {reajuste.evidencia_anexo_id, reajuste.apostilamento_anexo_id} | {m.pdf_anexo_id for m in reajuste.memorias} | {m.xlsx_anexo_id for m in reajuste.memorias}
    if anexo_id not in permitidos:
        raise RegistroNaoEncontrado("Arquivo")
    return servico_anexos.resposta_download(sessao.get(Anexo, anexo_id))
