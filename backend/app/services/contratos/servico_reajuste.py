# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de reajuste de preços, memória e apostilamento.
"""Reajuste de preços (tela 6): abertura, evidência do índice, memória, apostilamento e conclusão.

Regras: um reajuste em elaboração por vez; cada vigência é reajustada uma vez. Cada item tem o seu
percentual: positivo reajusta, negativo dá desconto, zero mantém o preço.

Competências já medidas mantêm os preços antigos (princípio da fotografia). Na conclusão, a diferença
líquida delas (quantidade medida × (preço novo − preço pago)):
- positiva: vira uma competência complementar ("diferença de reajuste") a pagar;
- negativa: vira um crédito da SPI, abatido no valor autorizado das próximas medições.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.anexo import Anexo
from app.models.contratos import Competencia, Contrato, ItemMedicao, ItemReajuste, MemoriaReajuste, Reajuste
from app.models.usuario import Usuario
from app.schemas.contratos.alteracoes import (
    AbatimentoLeitura,
    AberturaReajuste,
    GravacaoMemoriaReajuste,
    ItemReajusteLeitura,
    LeituraMemoriaVersao,
    LeituraReajuste,
    PainelReajuste,
    ResumoMesesReajuste,
    VigenciaDisponivel,
)
from app.schemas.contratos.execucao import LeituraArquivo
from app.services import servico_anexos
from app.services.contratos import calculos, valores
from app.services.contratos.documentos_execucao import moeda, moeda_unitaria, quantidade
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_configuracao_execucao import checklist_ativo, copiar_checklist
from app.services.contratos.servico_competencias import proxima_competencia_a_medir, registrar_credito_reajuste, sincronizar_competencia
from app.services.contratos.servico_contratos import exigir_edicao, obter_contrato, pode_editar, vigencias
from app.services.documentos.pdf import DocumentoPdf
from app.services.documentos.planilha import FORMATO_MOEDA, FORMATO_MOEDA_UNITARIA, FORMATO_QUANTIDADE, Aba, Coluna, gerar_planilha
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)
CEM = Decimal(100)
# Tipo MIME das planilhas .xlsx
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _arquivo(anexo: Anexo | None) -> LeituraArquivo | None:
    """Converte um anexo no formato de leitura da API (ou None)."""
    return LeituraArquivo(anexo_id=anexo.id, nome=anexo.nome_original, tamanho=anexo.tamanho, enviado_em=anexo.criado_em) if anexo else None


def _carregar(sessao: Session, contrato: Contrato) -> list[Reajuste]:
    """Reajustes do contrato com itens e memórias carregados, do mais antigo para o mais recente."""
    return list(
        sessao.scalars(
            select(Reajuste)
            .where(Reajuste.contrato_id == contrato.id)
            .options(selectinload(Reajuste.itens), selectinload(Reajuste.abatimentos),
                     selectinload(Reajuste.memorias).selectinload(MemoriaReajuste.pdf_anexo),
                     selectinload(Reajuste.memorias).selectinload(MemoriaReajuste.xlsx_anexo))
            .order_by(Reajuste.criado_em)
        )
    )


def _vigencia(contrato: Contrato, sequencia: int) -> calculos.Vigencia:
    """Vigência pelo número, ou `RegistroNaoEncontrado`."""
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
    # Base mensal: soma só dos itens contínuos (quantidade mensal × preço)
    base_atual = base_nova = ZERO
    for linha in reajuste.itens:
        if linha.tipo == "continuo":
            base_atual += linha.quantidade_mensal * linha.valor_unitario_atual
            base_nova += linha.quantidade_mensal * linha.valor_unitario_reajustado
    # Valor global simulado com os novos preços a partir do mês de referência
    novos = {linha.item_id: linha.valor_unitario_reajustado for linha in reajuste.itens}
    atual = valores.valor_global_vigencia(contrato, vigencia)
    reajuste.base_atual, reajuste.base_reajustada = calculos.arredondar(base_atual), calculos.arredondar(base_nova)
    reajuste.valor_global_atual = atual
    # No reajuste retroativo os preços novos valem na própria vigência retroativa, isto é, antes da data de efeito
    reajuste.valor_global_reajustado = valores.valor_global_vigencia(contrato, vigencia, (reajuste.efeito, novos), simulado_antes=reajuste.retroativo)


def _competencias_afetadas(contrato: Contrato, reajuste: Reajuste) -> list[Competencia]:
    """Competências regulares ainda não medidas a partir da referência: recebem o novo preço.

    No reajuste retroativo são todas as não medidas da vigência retroativa (os preços novos valem na vigência inteira).
    """
    return [
        c for c in contrato.competencias
        if c.tipo == "regular" and c.sequencia_vigencia == reajuste.sequencia_vigencia
        and (reajuste.retroativo or c.competencia >= reajuste.mes_referencia) and c.medicao_concluida_em is None
    ]


def _competencias_medidas(contrato: Contrato, reajuste: Reajuste) -> list[Competencia]:
    """Competências regulares já medidas a partir da referência e ainda sem diferença paga: a diferença delas é paga à parte.

    Mês anterior à referência não entra: foi faturado antes de o reajuste valer, no preço certo daquela época.
    `diferenca_coberta_por_reajuste_id` impede que um mês já acertado entre de novo.

    O reajuste retroativo não tem diferença a acertar: ele exige que a vigência retroativa ainda não tenha medição concluída.
    """
    if reajuste.retroativo:
        return []
    return sorted(
        (
            c for c in contrato.competencias
            if c.tipo == "regular"
            and c.sequencia_vigencia == reajuste.sequencia_vigencia
            and c.competencia >= reajuste.mes_referencia
            and c.diferenca_coberta_por_reajuste_id is None
            and c.medicao_concluida_em is not None
        ),
        key=lambda c: c.periodo_inicio,
    )


def rotulo_competencia(competencia: Competencia) -> str:
    """A competência como `AAAA-MM`."""
    return f"{competencia.competencia:%Y-%m}"


# Como calcular os meses quebrados (que contêm a data de efeito): uma escolha só, para todos os meses e itens do reajuste
MODOS_MES_QUEBRADO = ("pro_rata", "integral")


def _quebrado(competencia: Competencia, reajuste: Reajuste) -> bool:
    """Mês que contém a data de efeito: parte dele é do preço antigo, parte do novo."""
    return competencia.periodo_inicio < reajuste.efeito <= competencia.periodo_fim


def _dias(competencia: Competencia, efeito) -> tuple[int, int, int]:
    """Dias comerciais (30/360) do mês quebrado: antes do efeito, a partir dele e o total do período medido."""
    total = calculos.dias_comerciais(competencia.periodo_inicio, competencia.periodo_fim) or 1
    depois = calculos.dias_comerciais(efeito, competencia.periodo_fim)
    return total - depois, depois, total


def _fracao_apos_efeito(competencia: Competencia, linha, reajuste: Reajuste, modo: str | None = None) -> Decimal:
    """Quanto da quantidade medida da linha vale a diferença: tudo, nada ou a fração dos dias a partir da data de efeito.

    - Trecho de mês partido pela virada de vigência: só conta o trecho da vigência deste reajuste (o da vigência
      anterior é regido pelo reajuste dela), e só a partir do efeito.
    - Mês quebrado (contém o efeito): `integral` cobra o mês inteiro com o preço novo; `pro_rata`, só os dias a partir
      do efeito. Vale para todos os itens, inclusive os de faturamento sempre integral: a escolha do gestor manda.
      `modo` simula uma opção sem gravá-la; sem ele vale a escolha gravada e, enquanto não houver escolha, pro rata.
    - Mês inteiro: tudo se termina no efeito ou depois; nada se termina antes.

    O mês do fim da vigência já vem medido só até o último dia dela: as duas opções param ali, e a vigência
    seguinte (prorrogação) é tratada pelo reajuste dela.
    """
    efeito = reajuste.efeito
    if linha.periodo_inicio is not None:
        if linha.sequencia_vigencia != reajuste.sequencia_vigencia:
            return ZERO
        if competencia.periodo_fim < efeito:
            return Decimal(1)
        return Decimal(1) if linha.periodo_inicio >= efeito else ZERO
    if _quebrado(competencia, reajuste):
        if (modo or reajuste.calculo_mes_quebrado) == "integral":
            return Decimal(1)
        _, depois, total = _dias(competencia, efeito)
        return Decimal(depois) / Decimal(total)
    return Decimal(1) if competencia.periodo_fim >= efeito else ZERO


def _diferencas(contrato: Contrato, reajuste: Reajuste, novos: dict, modo: str | None = None) -> tuple[list[Competencia], dict, dict]:
    """Competências medidas desde a referência e, por item, a quantidade medida e o valor da diferença (só dos dias com o novo preço)."""
    medidas = _competencias_medidas(contrato, reajuste)
    quantidades: dict = {}
    valores_diferenca: dict = {}
    for competencia in medidas:
        for linha in competencia.itens:
            if linha.item_id not in novos or linha.quantidade_medida <= 0:
                continue
            quantidade = linha.quantidade_medida * _fracao_apos_efeito(competencia, linha, reajuste, modo)
            if quantidade <= 0:
                continue
            quantidades[linha.item_id] = quantidades.get(linha.item_id, ZERO) + quantidade
            valores_diferenca[linha.item_id] = valores_diferenca.get(linha.item_id, ZERO) + quantidade * (novos[linha.item_id] - linha.valor_unitario)
    return medidas, quantidades, valores_diferenca


@dataclass
class LinhaMes:
    """Um item numa competência já medida: o que foi pago, o que passa a valer e o que fica em haver (só dos dias com o novo preço)."""
    ordem: int
    descricao: str
    codigos: str
    quantidade: Decimal
    preco_pago: Decimal
    preco_novo: Decimal
    pago: Decimal
    reajustado: Decimal
    em_haver: Decimal


@dataclass
class MesDetalhe:
    """Uma competência medida desde a referência, com as linhas da memória e se a OB já foi paga."""
    rotulo: str
    identificador: str
    paga: bool
    linhas: list[LinhaMes]

    @property
    def pago(self) -> Decimal:
        return calculos.arredondar(sum((l.pago for l in self.linhas), ZERO))

    @property
    def reajustado(self) -> Decimal:
        return calculos.arredondar(sum((l.reajustado for l in self.linhas), ZERO))

    @property
    def em_haver(self) -> Decimal:
        return calculos.arredondar(sum((l.em_haver for l in self.linhas), ZERO))


_TIPOS = {"continuo": "Contínuo", "sob_demanda": "Sob demanda"}


def detalhe_meses(contrato: Contrato, reajuste: Reajuste, novos: dict | None = None) -> list[MesDetalhe]:
    """Memória mês a mês: para cada competência já medida a partir da referência, item a item, `quantidade × (preço novo − preço pago)`.

    Usa a mesma fração pós-efeito e a mesma conta de `_diferencas` (a soma de tudo é a diferença retroativa). "Paga" é a competência
    com a OB concluída; as medidas sem OB entram na lista com `paga = False`. Reajuste retroativo não tem mês medido."""
    novos = novos if novos is not None else {i.item_id: i.valor_unitario_reajustado for i in reajuste.itens}
    cadastro = {i.id: i for i in contrato.itens}
    meses = []
    for competencia in _competencias_medidas(contrato, reajuste):
        linhas = []
        for linha in sorted(competencia.itens, key=lambda l: (l.ordem, l.periodo_inicio or competencia.periodo_inicio)):
            if linha.item_id not in novos or linha.quantidade_medida <= 0:
                continue
            quantidade_pos = linha.quantidade_medida * _fracao_apos_efeito(competencia, linha, reajuste)
            if quantidade_pos <= 0:
                continue
            item = cadastro.get(linha.item_id)
            codigos = " · ".join([_TIPOS.get(linha.tipo, linha.tipo), (item.codigo_siafisico if item else "") or "—", (item.codigo_catmat_catser if item else "") or "—"])
            linhas.append(LinhaMes(
                ordem=linha.ordem, descricao=linha.descricao_completa, codigos=codigos,
                quantidade=quantidade_pos, preco_pago=linha.valor_unitario, preco_novo=novos[linha.item_id], pago=quantidade_pos * linha.valor_unitario,
                reajustado=quantidade_pos * novos[linha.item_id], em_haver=quantidade_pos * (novos[linha.item_id] - linha.valor_unitario),
            ))
        if linhas:
            meses.append(MesDetalhe(competencia.numero_competencia, competencia.identificador, competencia.etapa_atual == "concluida", linhas))
    return meses


def _trechos_do_item(competencia: Competencia, linha, preco_novo: Decimal, reajuste: Reajuste, modo: str) -> list[dict]:
    """Memória de um item no mês quebrado, período a período.

    Pro rata: os dias antes do efeito com o valor sem reajuste e os dias a partir dele com o valor reajustado.
    Integral: o período medido inteiro com o valor reajustado."""
    efeito = reajuste.efeito
    medida = linha.quantidade_medida
    if modo == "integral":
        _, _, total = _dias(competencia, efeito)
        return [{"inicio": competencia.periodo_inicio, "fim": competencia.periodo_fim, "dias": total, "reajustado": True,
                 "quantidade": medida, "valor_unitario": preco_novo, "valor": calculos.arredondar(medida * preco_novo)}]
    antes, depois, total = _dias(competencia, efeito)
    q_antes = medida * Decimal(antes) / Decimal(total)
    q_depois = medida * Decimal(depois) / Decimal(total)
    return [
        {"inicio": competencia.periodo_inicio, "fim": efeito - timedelta(days=1), "dias": antes, "reajustado": False,
         "quantidade": q_antes, "valor_unitario": linha.valor_unitario, "valor": calculos.arredondar(q_antes * linha.valor_unitario)},
        {"inicio": efeito, "fim": competencia.periodo_fim, "dias": depois, "reajustado": True,
         "quantidade": q_depois, "valor_unitario": preco_novo, "valor": calculos.arredondar(q_depois * preco_novo)},
    ]


def _opcao_mes_quebrado(competencia: Competencia, reajuste: Reajuste, novos: dict, modo: str) -> dict:
    """Uma opção (pro rata ou integral) de um mês quebrado: cada item com os trechos, o devido, o pago e o em haver."""
    itens = []
    for linha in sorted(competencia.itens, key=lambda l: l.ordem):
        if linha.item_id not in novos or linha.quantidade_medida <= 0 or linha.periodo_inicio is not None:
            continue
        trechos = _trechos_do_item(competencia, linha, novos[linha.item_id], reajuste, modo)
        pago = calculos.arredondar(linha.quantidade_medida * linha.valor_unitario)
        # Em haver pela mesma conta da diferença retroativa (quantidade alcançada × diferença de preço), para os totais baterem
        em_haver = calculos.arredondar(linha.quantidade_medida * _fracao_apos_efeito(competencia, linha, reajuste, modo) * (novos[linha.item_id] - linha.valor_unitario))
        itens.append({"ordem": linha.ordem, "descricao": linha.descricao_completa, "quantidade_medida": linha.quantidade_medida,
                      "valor_pago": pago, "trechos": trechos, "devido": calculos.arredondar(pago + em_haver), "em_haver": em_haver})
    return {
        "itens": itens,
        "valor_pago": calculos.arredondar(sum((i["valor_pago"] for i in itens), ZERO)),
        "devido": calculos.arredondar(sum((i["devido"] for i in itens), ZERO)),
        "em_haver": calculos.arredondar(sum((i["em_haver"] for i in itens), ZERO)),
    }


def meses_quebrados(contrato: Contrato, reajuste: Reajuste, novos: dict | None = None) -> list[dict]:
    """Meses medidos que contêm a data de efeito, com as duas opções calculadas para o gestor comparar e escolher."""
    if reajuste.retroativo:
        return []
    novos = novos if novos is not None else {i.item_id: i.valor_unitario_reajustado for i in reajuste.itens}
    return [
        {"competencia": rotulo_competencia(c), "rotulo": c.numero_competencia, "periodo_inicio": c.periodo_inicio, "periodo_fim": c.periodo_fim,
         "opcoes": {modo: _opcao_mes_quebrado(c, reajuste, novos, modo) for modo in MODOS_MES_QUEBRADO}}
        for c in _competencias_medidas(contrato, reajuste) if _quebrado(c, reajuste)
    ]


def resumo_meses(contrato: Contrato, reajuste: Reajuste) -> dict:
    """Resumo executivo: cada mês medido a partir da referência (com OB paga ou não) e o valor em haver, o total e os
    meses quebrados com as duas opções de cálculo."""
    meses = detalhe_meses(contrato, reajuste)
    diferenca = diferenca_retroativa(contrato, reajuste)
    quebrados = meses_quebrados(contrato, reajuste)
    return {
        "meses": [{"competencia": m.rotulo, "identificador": m.identificador, "paga": m.paga, "valor_pago": m.pago,
                   "valor_reajustado": m.reajustado, "em_haver": m.em_haver} for m in meses],
        "total_em_haver": diferenca if not reajuste.retroativo else ZERO,
        "diferenca_retroativa": diferenca,
        "meses_quebrados": quebrados,
        # Diferença retroativa inteira em cada opção: a escolha vale para todos os meses quebrados de uma vez
        "diferenca_pro_rata": diferenca_retroativa(contrato, reajuste, "pro_rata") if quebrados else diferenca,
        "diferenca_integral": diferenca_retroativa(contrato, reajuste, "integral") if quebrados else diferenca,
        "calculo_mes_quebrado": reajuste.calculo_mes_quebrado,
        "precisa_escolher": bool(quebrados) and reajuste.calculo_mes_quebrado is None,
    }


def competencias_medidas_na_vigencia(contrato: Contrato, reajuste: Reajuste) -> list[Competencia]:
    """Competências regulares da vigência do reajuste com medição concluída (impedem o reajuste retroativo)."""
    return [c for c in contrato.competencias if c.tipo == "regular" and c.sequencia_vigencia == reajuste.sequencia_vigencia and c.medicao_concluida_em is not None]


def diferenca_retroativa(contrato: Contrato, reajuste: Reajuste, modo: str | None = None) -> Decimal:
    """Diferença líquida das competências já medidas: > 0 a pagar à contratada, < 0 crédito da SPI (`modo` simula uma opção do mês quebrado)."""
    _, _, valores_diferenca = _diferencas(contrato, reajuste, {i.item_id: i.valor_unitario_reajustado for i in reajuste.itens}, modo)
    return calculos.arredondar(sum(valores_diferenca.values(), ZERO))


def gerar_competencia_diferenca(contrato: Contrato, reajuste: Reajuste, novos: dict) -> Competencia | None:
    """Competência complementar (`diferenca_reajuste`) com a diferença de preço das quantidades já medidas.

    Por item: quantidade = soma das medições concluídas desde a referência; valor unitário = preço
    reajustado − preço fotografado na competência (média ponderada, se houver preços diferentes).
    A medição já vem preenchida e segue o fluxo normal: NEs e ciências, nota fiscal, CADIN,
    checklist, consolidado e Ordem Bancária (sem avaliação).
    """
    # Soma, por item, as quantidades medidas e o valor da diferença (quantidade × (novo − antigo))
    medidas, quantidades, valores_diferenca = _diferencas(contrato, reajuste, novos)
    # Só há competência complementar com diferença líquida a pagar (a negativa vira crédito)
    if not quantidades or calculos.arredondar(sum(valores_diferenca.values(), ZERO)) <= 0:
        return None
    # Itens sem diferença não entram; itens com desconto entram com preço negativo (o total é líquido)
    quantidades = {k: v for k, v in quantidades.items() if calculos.arredondar(valores_diferenca[k]) != 0}
    itens = {i.id: i for i in contrato.itens}
    competencia = Competencia(
        tipo="diferenca_reajuste", reajuste_id=reajuste.id, competencia=reajuste.mes_referencia,
        periodo_inicio=medidas[0].periodo_inicio, periodo_fim=medidas[-1].periodo_fim,
        sequencia_vigencia=reajuste.sequencia_vigencia, etapa_atual="medicao",
    )
    # Preço unitário da diferença = valor total da diferença ÷ quantidade total (média ponderada)
    for item_id, total_medido in quantidades.items():
        item = itens[item_id]
        unitario = (valores_diferenca[item_id] / total_medido).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        competencia.itens.append(
            ItemMedicao(
                item_id=item_id, ordem=item.ordem, descricao=f"{item.descricao} (diferença de reajuste)", tipo=item.tipo,
                calcula_pro_rata=item.calcula_pro_rata, valor_unitario=unitario, fator_meses=Decimal(len(medidas)),
                quantidade_prevista=total_medido, quantidade_medida=total_medido,
            )
        )
    # A complementar também precisa do checklist mensal
    checklist = checklist_ativo(contrato)
    if checklist:
        copiar_checklist(competencia, checklist)
    contrato.competencias.append(competencia)
    # Marcar as competências de origem como cobertas por este reajuste,
    # para que reajustes futuros não as incluam de novo na diferença
    for c in medidas:
        c.diferenca_coberta_por_reajuste_id = reajuste.id
    return competencia


def leitura(contrato: Contrato, reajuste: Reajuste, anexos: dict) -> LeituraReajuste:
    """Converte o reajuste para o formato de leitura (as contagens de competências só valem em elaboração)."""
    rascunho = reajuste.situacao == "rascunho"
    diferenca = diferenca_retroativa(contrato, reajuste) if rascunho else (reajuste.diferenca_retroativa or ZERO)
    # Prévia do destino do crédito (rascunho) ou onde ele foi abatido (concluído)
    destino = proxima_competencia_a_medir(contrato) if rascunho and diferenca < 0 else None
    abatimentos = [a for a in reajuste.abatimentos if a.valor > 0]
    resumo = resumo_meses(contrato, reajuste) if rascunho else None
    return LeituraReajuste(
        resumo_meses=ResumoMesesReajuste(**{k: v for k, v in resumo.items() if k != "diferenca_retroativa"}) if resumo else None,
        diferenca_retroativa=diferenca,
        competencia_credito=destino.numero_competencia if destino else None,
        abatimentos=[
            AbatimentoLeitura(competencia=a.competencia.numero_competencia, identificador=a.competencia.identificador,
                              medida=a.competencia.medicao_concluida_em is not None, valor=a.valor)
            for a in abatimentos if a.competencia is not None
        ],
        credito_pendente=calculos.arredondar(sum((a.valor for a in abatimentos if a.competencia is None), ZERO)),
        id=reajuste.id, situacao=reajuste.situacao, retroativo=reajuste.retroativo, sequencia_vigencia=reajuste.sequencia_vigencia, vigencia_inicio=reajuste.vigencia_inicio,
        vigencia_fim=reajuste.vigencia_fim, mes_referencia=reajuste.mes_referencia, data_efeito=reajuste.efeito,
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
    """Reajuste em elaboração, vigências que ainda podem ser reajustadas e o histórico."""
    contrato = obter_contrato(sessao, contrato_id)
    reajustes = _carregar(sessao, contrato)
    # Anexos (evidência e apostilamento) de todos os reajustes em uma consulta
    ids = [x for r in reajustes for x in (r.evidencia_anexo_id, r.apostilamento_anexo_id) if x]
    anexos = {a.id: a for a in sessao.scalars(select(Anexo).where(Anexo.id.in_(ids)))}
    # Vigências já reajustadas não aparecem como opção
    reajustadas = {r.sequencia_vigencia for r in reajustes if r.situacao == "concluido" and not r.retroativo}
    em_andamento = next((r for r in reajustes if r.situacao == "rascunho"), None)
    return PainelReajuste(
        em_andamento=leitura(contrato, em_andamento, anexos) if em_andamento else None,
        vigencias_disponiveis=[
            VigenciaDisponivel(sequencia=v.sequencia, inicio=v.inicio, fim=v.fim) for v in vigencias(contrato) if v.sequencia not in reajustadas
        ],
        vigencias_retroativas_disponiveis=[
            VigenciaDisponivel(sequencia=v.sequencia, inicio=v.inicio, fim=v.fim) for v in [_proxima_retroativa(contrato, reajustes)] if v is not None
        ],
        historico=[leitura(contrato, r, anexos) for r in reajustes if r.situacao != "rascunho"],
        pode_editar=pode_editar(sessao, contrato, usuario),
    )


def _proxima_retroativa(contrato: Contrato, reajustes: list[Reajuste]) -> calculos.Vigencia | None:
    """Vigência retroativa que aceita o reajuste retroativo agora: a mais recente ainda sem ele.

    Os preços de cada vigência retroativa saem dos da vigência seguinte, então a cadeia é feita da mais recente para a mais antiga.
    """
    feitas = {r.sequencia_vigencia for r in reajustes if r.retroativo and r.situacao == "concluido"}
    pendentes = [v for v in vigencias(contrato) if v.retroativa and v.sequencia not in feitas]
    return pendentes[-1] if pendentes else None


def _em_andamento(sessao: Session, contrato: Contrato, reajuste_id: uuid.UUID) -> Reajuste:
    """Reajuste pelo id, desde que ainda esteja em elaboração."""
    reajuste = next((r for r in _carregar(sessao, contrato) if r.id == reajuste_id), None)
    if reajuste is None:
        raise RegistroNaoEncontrado("Reajuste")
    if reajuste.situacao != "rascunho":
        raise ErroRegraContrato("Este reajuste não está mais em elaboração.")
    return reajuste


def abrir(sessao: Session, contrato_id: uuid.UUID, dados: AberturaReajuste, autor: Usuario) -> None:
    """Abre um reajuste para a vigência escolhida, fotografando os itens com os preços atuais."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    existentes = _carregar(sessao, contrato)
    if any(r.situacao == "rascunho" for r in existentes):
        raise ErroRegraContrato("Já existe um reajuste em elaboração. Conclua ou cancele-o antes.", conflito=True)
    if any(r.situacao == "concluido" and r.retroativo == dados.retroativo and r.sequencia_vigencia == dados.sequencia_vigencia for r in existentes):
        raise ErroRegraContrato("Esta vigência já foi reajustada.")
    vigencia = _vigencia(contrato, dados.sequencia_vigencia)
    if dados.retroativo:
        proxima = _proxima_retroativa(contrato, existentes)
        if not vigencia.retroativa:
            raise ErroRegraContrato("O reajuste retroativo só vale para vigências retroativas.")
        if proxima is None:
            raise ErroRegraContrato("Todas as vigências retroativas já têm reajuste retroativo.")
        if vigencia.sequencia != proxima.sequencia:
            raise ErroRegraContrato(f"Faça o reajuste retroativo da {proxima.sequencia}ª vigência antes: os preços voltam no tempo uma vigência por vez.")
        if any(c.tipo == "regular" and c.sequencia_vigencia == vigencia.sequencia and c.medicao_concluida_em is not None for c in contrato.competencias):
            raise ErroRegraContrato("A vigência retroativa já tem competência medida: o reajuste retroativo precisa vir antes das medições.")
        # Os preços novos valem na vigência retroativa inteira; o preço de partida é o da vigência seguinte, que começa na data de efeito
        efeito = vigencia.fim + timedelta(days=1)
    elif dados.data_efeito is not None:
        efeito = dados.data_efeito
        if not vigencia.inicio <= efeito <= vigencia.fim:
            raise ErroRegraContrato("A data de efeito precisa estar dentro da vigência escolhida.")
    else:
        efeito = calculos.primeiro_dia(dados.mes_referencia)  # type: ignore[arg-type]
        if not calculos.primeiro_dia(vigencia.inicio) <= efeito <= vigencia.fim:
            raise ErroRegraContrato("O mês de referência precisa estar dentro da vigência escolhida.")
    referencia = calculos.primeiro_dia(efeito)
    reajuste = Reajuste(
        contrato_id=contrato.id, sequencia_vigencia=vigencia.sequencia, vigencia_inicio=vigencia.inicio, vigencia_fim=vigencia.fim,
        mes_referencia=referencia, data_efeito=efeito, criado_por_id=autor.id, retroativo=dados.retroativo,
    )
    # Cada item começa com índice 0 (preço reajustado = preço atual na data de efeito)
    for item in contrato.itens:
        preco = valores.preco_em(contrato, item, efeito)
        reajuste.itens.append(
            ItemReajuste(
                item_id=item.id, ordem=item.ordem, descricao=item.descricao, tipo=item.tipo,
                quantidade_mensal=valores.quantidade_mensal_em(contrato, item, calculos.primeiro_dia(vigencia.inicio) if dados.retroativo else referencia),
                valor_unitario_atual=preco,
                indice_percentual=ZERO, valor_unitario_reajustado=preco,
            )
        )
    sessao.add(reajuste)
    calcular_totais(contrato, reajuste)
    auditar(sessao, autor.login, "contrato.reajuste.abrir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"vigencia": vigencia.sequencia, "mes_referencia": referencia, "data_efeito": efeito,
                                                        "retroativo": dados.retroativo})
    sessao.commit()


def anexar_evidencia(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Anexa (ou substitui) o PDF que comprova o índice usado."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-reajuste-evidencia", autor.id, contrato_id=contrato.id)
    sessao.flush()
    reajuste.evidencia_anexo_id = anexo.id
    auditar(sessao, autor.login, "contrato.reajuste.evidencia", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
    sessao.commit()


def reajustar_preco(atual: Decimal, indice: Decimal, referencial: Decimal | None) -> Decimal:
    """Preço × (1 + índice/100), com 4 casas (como o preço unitário); o valor referencial, quando informado, é o teto."""
    novo = (atual * (1 + indice / CEM)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return min(novo, referencial) if referencial is not None else novo


def deflacionar_preco(atual: Decimal, indice: Decimal, referencial: Decimal | None) -> Decimal:
    """Reajuste retroativo: preço ÷ (1 + índice/100), com 4 casas; o valor referencial, quando informado, é o piso."""
    if indice <= -CEM:
        raise ErroRegraContrato("O índice precisa ser maior que -100%.")
    anterior = (atual / (1 + indice / CEM)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return max(anterior, referencial) if referencial is not None else anterior


def aplicar_calculo_mes_quebrado(contrato: Contrato, reajuste: Reajuste, modo: str | None) -> None:
    """Grava como calcular os meses quebrados (`pro_rata` ou `integral`), uma escolha para todos; `None` mantém a atual.

    Só aceita a escolha quando há mês quebrado: sem ele as duas opções dão o mesmo valor e a escolha esconderia um engano."""
    if modo is None:
        return
    if not meses_quebrados(contrato, reajuste):
        raise ErroRegraContrato("Este reajuste não tem mês quebrado pela data de efeito: não há o que escolher.")
    reajuste.calculo_mes_quebrado = modo


def salvar_memoria(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, dados: GravacaoMemoriaReajuste, autor: Usuario) -> None:
    """Grava índice e teto de cada item, a escolha do cálculo dos meses quebrados, recalcula os novos preços e os totais."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    linhas = {i.item_id: i for i in reajuste.itens}
    if {i.item_id for i in dados.itens} - set(linhas):
        raise ErroRegraContrato("Um dos itens não pertence a este reajuste.")
    for entrada in dados.itens:
        linha = linhas[entrada.item_id]
        linha.indice_percentual, linha.valor_referencial = entrada.indice_percentual, entrada.valor_referencial
        calcular = deflacionar_preco if reajuste.retroativo else reajustar_preco
        linha.valor_unitario_reajustado = calcular(linha.valor_unitario_atual, entrada.indice_percentual, entrada.valor_referencial)
    # Depois dos preços: a validação compara os dois cenários, que dependem do novo preço
    aplicar_calculo_mes_quebrado(contrato, reajuste, dados.calculo_mes_quebrado)
    calcular_totais(contrato, reajuste)
    auditar(sessao, autor.login, "contrato.reajuste.memoria", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"itens": {str(i.item_id): {"indice": i.indice_percentual, "novo": i.valor_unitario_reajustado} for i in reajuste.itens}})
    sessao.commit()


def previa_memoria(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, dados: GravacaoMemoriaReajuste, autor: Usuario) -> LeituraReajuste:
    """Calculadora ao vivo: o reajuste como ficaria com estes índices e tetos (preços, totais, diferença e meses pagos), **sem gravar nada**.

    Aplica os valores nas linhas em memória, calcula tudo como `salvar_memoria` e desfaz (`rollback`)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    linhas = {i.item_id: i for i in reajuste.itens}
    if {i.item_id for i in dados.itens} - set(linhas):
        raise ErroRegraContrato("Um dos itens não pertence a este reajuste.")
    try:
        for entrada in dados.itens:
            linha = linhas[entrada.item_id]
            linha.indice_percentual, linha.valor_referencial = entrada.indice_percentual, entrada.valor_referencial
            calcular = deflacionar_preco if reajuste.retroativo else reajustar_preco
            linha.valor_unitario_reajustado = calcular(linha.valor_unitario_atual, entrada.indice_percentual, entrada.valor_referencial)
        # Depois dos preços: a validação compara os dois cenários, que dependem do novo preço
        aplicar_calculo_mes_quebrado(contrato, reajuste, dados.calculo_mes_quebrado)
        calcular_totais(contrato, reajuste)
        return leitura(contrato, reajuste, {})
    finally:
        sessao.rollback()


# Versão do layout dos arquivos da memória: ao mudar o layout (colunas, quebras de página), sobe e a próxima geração cria uma versão nova com o layout atual
FORMATO_MEMORIA = 6


def gerar_arquivos_memoria(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, autor: Usuario) -> None:
    """PDF e XLSX da memória; nova versão só se os dados mudaram."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    if reajuste.calculo_mes_quebrado is None and meses_quebrados(contrato, reajuste):
        raise ErroRegraContrato("Escolha como calcular os meses quebrados (pro rata ou integral) antes de gerar a memória.")
    # Hash dos dados da memória: se nada mudou desde a última versão, não gera arquivos novos
    origem = hashlib.sha256(json.dumps(
        [[str(i.item_id), str(i.valor_unitario_atual), str(i.indice_percentual), str(i.valor_referencial), str(i.valor_unitario_reajustado)] for i in reajuste.itens]
        + [str(reajuste.mes_referencia), str(reajuste.efeito), str(reajuste.calculo_mes_quebrado), FORMATO_MEMORIA]
        # A memória mês a mês também entra: medição, preço pago e OB concluída de cada mês mudam o que está em haver
        + [[m.identificador, m.paga, str(m.pago), str(m.em_haver)] for m in detalhe_meses(contrato, reajuste)]
    ).encode()).hexdigest()
    if reajuste.memorias and reajuste.memorias[-1].hash_origem == origem:
        return
    versao = len(reajuste.memorias) + 1
    base = f"memoria-reajuste-{contrato.numero_arquivo}-v{versao}"
    pdf = servico_anexos.guardar_pdf_gerado(sessao, _pdf_memoria(contrato, reajuste, versao, autor), f"{base}.pdf", "contrato-reajuste-memoria", autor.id, contrato_id=contrato.id)
    xlsx = servico_anexos.guardar_arquivo_gerado(sessao, _xlsx_memoria(contrato, reajuste), f"{base}.xlsx", XLSX, "contrato-reajuste-memoria", autor.id, contrato_id=contrato.id)
    reajuste.memorias.append(MemoriaReajuste(versao=versao, pdf_anexo=pdf, xlsx_anexo=xlsx, hash_origem=origem, criado_por_id=autor.id, criado_em=agora_utc()))
    auditar(sessao, autor.login, "contrato.reajuste.memoria.gerar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"versao": versao})
    sessao.commit()


def _linhas(reajuste: Reajuste) -> list[list]:
    """Linhas da tabela da memória (usadas no PDF e na planilha); a variação é negativa no desconto."""
    return [
        [i.ordem, i.descricao, i.quantidade_mensal, i.valor_unitario_atual, i.indice_percentual, i.valor_referencial, i.valor_unitario_reajustado,
         i.valor_unitario_reajustado - i.valor_unitario_atual, calculos.arredondar(i.quantidade_mensal * i.valor_unitario_reajustado)]
        for i in reajuste.itens
    ]


def _percentual(valor: Decimal) -> str:
    """+2,0000% / -3,0000% / 0,0000%."""
    texto = f"{abs(valor):.4f}".replace(".", ",") + "%"
    return ("+" if valor > 0 else "-" if valor < 0 else "") + texto


def _moeda_com_sinal(valor: Decimal, unitario: bool = False) -> str:
    """+R$ 0,53 / -R$ 100,00 / R$ 0,00 (`unitario`: de 2 a 4 casas, como o preço unitário)."""
    return ("+" if valor > 0 else "-" if valor < 0 else "") + (moeda_unitaria if unitario else moeda)(abs(valor))


def _texto_diferenca(contrato: Contrato, reajuste: Reajuste) -> str:
    """Destino da diferença retroativa, para os totais da memória."""
    diferenca = diferenca_retroativa(contrato, reajuste)
    if diferenca > 0:
        return f"{moeda(diferenca)} a pagar em competência de diferença de reajuste"
    if diferenca < 0:
        destino = proxima_competencia_a_medir(contrato)
        onde = f"na medição de {destino.numero_competencia}" if destino else "na próxima competência gerada"
        return f"crédito de {moeda(-diferenca)} da SPI, abatido {onde}"
    return "sem diferença (nenhuma competência medida a partir da referência)"


def _pdf_memoria(contrato: Contrato, reajuste: Reajuste, versao: int, autor: Usuario) -> bytes:
    """Monta o PDF da memória de cálculo: identificação, itens e totais."""
    titulo = "Memória de cálculo do reajuste retroativo" if reajuste.retroativo else "Memória de cálculo do reajuste"
    documento = DocumentoPdf(titulo, f"Contrato {contrato.numero} · {reajuste.sequencia_vigencia}ª vigência · versão {versao}",
                             paisagem=True, autor=autor.nome_completo or autor.login)
    documento.secao("Identificação").campos([
        ("Contrato", contrato.numero), ("Contratada", contrato.empresa.razao_social),
        ("Vigência", f"{reajuste.vigencia_inicio:%d/%m/%Y} a {reajuste.vigencia_fim:%d/%m/%Y}"),
        ("Valores retroativos até" if reajuste.retroativo else "Novos valores a partir de", f"{(reajuste.efeito - timedelta(days=1)) if reajuste.retroativo else reajuste.efeito:%d/%m/%Y}"),
    ])
    documento.nova_pagina().secao(
        "Itens (índice do reajuste que levou à vigência seguinte; preço retroativo = valor ÷ (1 + índice), com o referencial como piso)" if reajuste.retroativo
        else "Itens (percentual positivo = reajuste; negativo = desconto)"
    ).tabela(
        ["Item", "Descrição", "Qtd. mensal", "Valor atual", "Índice (%)", "Referencial", "Valor reajustado", "Variação", "Subtotal reajustado"],
        [[str(l[0]), l[1], quantidade(l[2]), moeda_unitaria(l[3]), _percentual(l[4]), moeda_unitaria(l[5]) if l[5] is not None else "—",
          moeda_unitaria(l[6]), _moeda_com_sinal(l[7], unitario=True), moeda(l[8])]
         for l in _linhas(reajuste)],
        larguras=[0.7, 3.4, 1.1, 1.3, 1.1, 1.3, 1.4, 1.2, 1.5], alinhar_direita=[2, 3, 4, 5, 6, 7, 8],
    )
    documento.secao("Totais").campos([
        ("Base atual", moeda(reajuste.base_atual)), ("Nova base por competência", moeda(reajuste.base_reajustada)),
        ("Valor global atual", moeda(reajuste.valor_global_atual)), ("Novo valor global", moeda(reajuste.valor_global_reajustado)),
        ("Competências já medidas", _texto_diferenca(contrato, reajuste)),
    ])
    _secao_quebrados_pdf(documento, contrato, reajuste)
    _secoes_meses_pdf(documento, contrato, reajuste)
    return documento.gerar()


CABECALHO_MES = ["Nº", "Descrição", "Tipo · SIAFÍSICO · CATMAT/CATSER", "Qtd.", "Valor unit.", "Valor unit. reaj.", "Dif. +/−", "Valor pago", "Valor reajustado", "Em haver"]


def _linhas_mes(mes: MesDetalhe) -> list[list]:
    return [[l.ordem, l.descricao, l.codigos, l.quantidade, l.preco_pago, l.preco_novo, l.preco_novo - l.preco_pago, calculos.arredondar(l.pago),
             calculos.arredondar(l.reajustado), calculos.arredondar(l.em_haver)] for l in mes.linhas]


def _ob(mes: dict | MesDetalhe) -> str:
    """Situação da OB do mês medido, para os títulos e a coluna do resumo."""
    paga = mes["paga"] if isinstance(mes, dict) else mes.paga
    return "OB paga" if paga else "medida, aguardando OB"


def _texto_resumo(contrato: Contrato, reajuste: Reajuste) -> list[str]:
    """Texto do resumo executivo quando não há mês medido (ou no retroativo), e a linha do destino da diferença."""
    if reajuste.retroativo:
        return ["Não há meses medidos nesta vigência retroativa: nada em haver."]
    if not resumo_meses(contrato, reajuste)["meses"]:
        return ["Nenhum mês medido a partir da referência: nada em haver."]
    return [f"Diferença retroativa total: {_texto_diferenca(contrato, reajuste)}"]


ROTULOS_MODO = {"pro_rata": "Pro rata (dias antes do efeito sem reajuste, a partir dele reajustados)", "integral": "Integral (mês inteiro reajustado)"}
CABECALHO_QUEBRADO = ["Mês", "Item", "Descrição", "Período", "Dias", "Qtd.", "Valor unit.", "Valor"]


def _linhas_quebrados(contrato: Contrato, reajuste: Reajuste) -> tuple[list[list], list[dict]]:
    """Linhas período a período dos meses quebrados na opção escolhida (PDF e planilha) e os meses, para os subtotais."""
    linhas, meses = [], []
    for mes in meses_quebrados(contrato, reajuste):
        opcao = mes["opcoes"][reajuste.calculo_mes_quebrado or "pro_rata"]
        for item in opcao["itens"]:
            for t in item["trechos"]:
                periodo = f"{t['inicio']:%d/%m} a {t['fim']:%d/%m/%Y}" + ("" if t["reajustado"] else " (sem reajuste)")
                linhas.append([mes["rotulo"], item["ordem"], item["descricao"], periodo, t["dias"], t["quantidade"], t["valor_unitario"], t["valor"]])
        meses.append({"rotulo": mes["rotulo"], **opcao})
    return linhas, meses


def _secao_quebrados_pdf(documento: DocumentoPdf, contrato: Contrato, reajuste: Reajuste) -> None:
    """Meses quebrados pela data de efeito: a opção escolhida e a memória período a período."""
    linhas, meses = _linhas_quebrados(contrato, reajuste)
    if not linhas:
        return
    secao = documento.nova_pagina().secao(f"Meses quebrados pela data de efeito ({reajuste.efeito:%d/%m/%Y})")
    secao.paragrafo(f"Cálculo escolhido: {ROTULOS_MODO[reajuste.calculo_mes_quebrado or 'pro_rata']}.")
    secao.tabela(
        CABECALHO_QUEBRADO,
        [[l[0], str(l[1]), l[2], l[3], str(l[4]), quantidade(l[5]), moeda_unitaria(l[6]), moeda(l[7])] for l in linhas],
        larguras=[1.1, 0.6, 4.2, 2.6, 0.7, 1.1, 1.3, 1.4], alinhar_direita=[4, 5, 6, 7],
    )
    for m in meses:
        documento.paragrafo(f"{m['rotulo']}: devido {moeda(m['devido'])} − pago {moeda(m['valor_pago'])} = em haver {moeda(m['em_haver'])}")


def _secoes_meses_pdf(documento: DocumentoPdf, contrato: Contrato, reajuste: Reajuste) -> None:
    """Uma seção por mês medido (item a item, com a situação da OB) e o resumo executivo."""
    larguras = [0.55, 2.8, 2.3, 0.9, 1.2, 1.3, 1.2, 1.4, 1.5, 1.3]
    for mes in detalhe_meses(contrato, reajuste):
        linhas = _linhas_mes(mes)
        documento.nova_pagina().secao(f"Memória de {mes.rotulo} ({_ob(mes)})").tabela(
            CABECALHO_MES,
            [[str(l[0]), l[1], l[2], quantidade(l[3]), moeda_unitaria(l[4]), moeda_unitaria(l[5]), _moeda_com_sinal(l[6], unitario=True), moeda(l[7]), moeda(l[8]), moeda(l[9])] for l in linhas],
            larguras=larguras, alinhar_direita=[3, 4, 5, 6, 7, 8, 9], rodape=["", f"Subtotal {mes.rotulo}", "", "", "", "", "", moeda(mes.pago), moeda(mes.reajustado), moeda(mes.em_haver)],
        )
    secao = documento.nova_pagina().secao("Memória de cálculo executiva")
    resumo = resumo_meses(contrato, reajuste)
    if reajuste.retroativo or not resumo["meses"]:
        for texto in _texto_resumo(contrato, reajuste):
            secao.paragrafo(texto)
        return
    # Tabela: um mês medido por linha, com a situação da OB e o total no rodapé; o destino da diferença vem em texto, abaixo
    secao.tabela(
        ["Mês", "OB", "Valor pago", "Valor reajustado", "Em haver"],
        [[m["competencia"], _ob(m), moeda(m["valor_pago"]), moeda(m["valor_reajustado"]), moeda(m["em_haver"])] for m in resumo["meses"]],
        larguras=[1.2, 2.2, 2, 2, 2], alinhar_direita=[2, 3, 4],
        rodape=["Total em haver", "", moeda(sum((m["valor_pago"] for m in resumo["meses"]), ZERO)), moeda(sum((m["valor_reajustado"] for m in resumo["meses"]), ZERO)), moeda(resumo["total_em_haver"])],
    )
    documento.espaco(4)
    for texto in _texto_resumo(contrato, reajuste):
        documento.paragrafo(texto)


def _xlsx_memoria(contrato: Contrato, reajuste: Reajuste) -> bytes:
    """Monta a planilha da memória de cálculo com as mesmas colunas do PDF (aba "Reajuste", uma aba por mês medido e a aba "Resumo")."""
    abas = _abas_itens(contrato, reajuste)
    for mes in detalhe_meses(contrato, reajuste):
        abas.append(Aba(
            mes.rotulo.replace("/", "-"),
            [Coluna("Item", largura=6), Coluna("Descrição", largura=40), Coluna("Tipo · SIAFÍSICO · CATMAT/CATSER", largura=30), Coluna("Qtd.", FORMATO_QUANTIDADE),
             Coluna("Valor unit.", FORMATO_MOEDA_UNITARIA), Coluna("Valor unit. reaj.", FORMATO_MOEDA_UNITARIA), Coluna("Dif. +/−", FORMATO_MOEDA_UNITARIA),
             Coluna("Valor pago", FORMATO_MOEDA, 16), Coluna("Valor reajustado", FORMATO_MOEDA, 16), Coluna("Em haver", FORMATO_MOEDA, 16)],
            _linhas_mes(mes), titulo=f"Memória de {mes.rotulo} ({_ob(mes)}) — Contrato {contrato.numero}",
            rodape=["", f"Subtotal {mes.rotulo}", "", "", "", "", "", mes.pago, mes.reajustado, mes.em_haver],
        ))
    linhas_quebrados, meses_q = _linhas_quebrados(contrato, reajuste)
    if linhas_quebrados:
        abas.append(Aba(
            "Meses quebrados",
            [Coluna("Mês", largura=12), Coluna("Item", largura=6), Coluna("Descrição", largura=40), Coluna("Período", largura=26), Coluna("Dias", largura=6),
             Coluna("Qtd.", FORMATO_QUANTIDADE), Coluna("Valor unit.", FORMATO_MOEDA_UNITARIA), Coluna("Valor", FORMATO_MOEDA, 16)],
            linhas_quebrados, titulo=f"Meses quebrados pela data de efeito ({reajuste.efeito:%d/%m/%Y}) — Contrato {contrato.numero}",
            observacoes=[f"Cálculo escolhido: {ROTULOS_MODO[reajuste.calculo_mes_quebrado or 'pro_rata']}."]
            + [f"{m['rotulo']}: devido {moeda(m['devido'])} − pago {moeda(m['valor_pago'])} = em haver {moeda(m['em_haver'])}" for m in meses_q],
        ))
    resumo = resumo_meses(contrato, reajuste)
    if reajuste.retroativo or not resumo["meses"]:
        abas.append(Aba("Resumo", [Coluna("Memória de cálculo executiva", largura=110)], [[t] for t in _texto_resumo(contrato, reajuste)],
                        titulo=f"Resumo executivo — Contrato {contrato.numero}"))
    else:
        abas.append(Aba(
            "Resumo", [Coluna("Mês", largura=14), Coluna("OB", largura=24), Coluna("Valor pago", FORMATO_MOEDA, 18), Coluna("Valor reajustado", FORMATO_MOEDA, 18),
                       Coluna("Em haver", FORMATO_MOEDA, 18)],
            [[m["competencia"], _ob(m), m["valor_pago"], m["valor_reajustado"], m["em_haver"]] for m in resumo["meses"]],
            titulo=f"Memória de cálculo executiva — Contrato {contrato.numero}",
            rodape=["Total em haver", "", sum((m["valor_pago"] for m in resumo["meses"]), ZERO), sum((m["valor_reajustado"] for m in resumo["meses"]), ZERO), resumo["total_em_haver"]],
            observacoes=_texto_resumo(contrato, reajuste),
        ))
    return gerar_planilha(abas)


def _abas_itens(contrato: Contrato, reajuste: Reajuste) -> list[Aba]:
    """Aba "Reajuste": itens, preço atual e reajustado."""
    return [Aba(
        "Reajuste",
        [Coluna("Item", largura=6), Coluna("Descrição", largura=40), Coluna("Qtd. mensal", FORMATO_QUANTIDADE), Coluna("Valor atual", FORMATO_MOEDA_UNITARIA),
         Coluna("Índice (%)", "+0.0000;-0.0000;0.0000"), Coluna("Referencial", FORMATO_MOEDA_UNITARIA), Coluna("Valor reajustado", FORMATO_MOEDA_UNITARIA),
         Coluna("Variação", FORMATO_MOEDA_UNITARIA), Coluna("Subtotal reajustado", FORMATO_MOEDA, 20)],
        _linhas(reajuste),
        titulo=f"Memória de cálculo do reajuste — Contrato {contrato.numero} — a partir de {reajuste.efeito:%d/%m/%Y}",
        observacoes=["Índice: percentual positivo = reajuste; negativo = desconto.",
                     f"Base atual: {moeda(reajuste.base_atual)} · Nova base: {moeda(reajuste.base_reajustada)}",
                     f"Valor global atual: {moeda(reajuste.valor_global_atual)} · Novo valor global: {moeda(reajuste.valor_global_reajustado)}",
                     f"Competências já medidas: {_texto_diferenca(contrato, reajuste)}"],
    )]


def concluir(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Anexa o apostilamento e aplica os preços: itens, competências ainda não medidas e valor global."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    # Exige a evidência do índice e ao menos uma memória gerada
    if reajuste.evidencia_anexo_id is None:
        raise ErroRegraContrato("Anexe a evidência do índice antes de concluir.")
    if not reajuste.memorias:
        raise ErroRegraContrato("Gere a memória de cálculo (PDF/XLSX) antes de concluir.")
    if reajuste.retroativo and competencias_medidas_na_vigencia(contrato, reajuste):
        raise ErroRegraContrato("A vigência retroativa já tem competência medida: o reajuste retroativo precisa vir antes das medições.")
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-reajuste-apostilamento", autor.id, contrato_id=contrato.id)
    sessao.flush()
    reajuste.apostilamento_anexo_id = anexo.id
    # O preço do cadastro só muda se o reajuste for da vigência atual (a última)
    novos = {i.item_id: i.valor_unitario_reajustado for i in reajuste.itens}
    ultima_vigencia = vigencias(contrato)[-1].sequencia
    for item in contrato.itens:
        if item.id in novos and reajuste.sequencia_vigencia == ultima_vigencia:
            item.valor_unitario = novos[item.id]
    # Competências ainda não medidas passam a usar o novo preço: as linhas são refeitas pelo cadastro, já com a data de efeito
    # (o mês da virada ganha uma linha por trecho). Precisa vir depois de marcar o reajuste como concluído.
    afetadas = _competencias_afetadas(contrato, reajuste)
    diferenca_ate_aqui = diferenca_retroativa(contrato, reajuste)
    reajuste.situacao = "concluido"
    for competencia in afetadas:
        sincronizar_competencia(contrato, competencia)
    # O valor global reajustado do contrato também só vale para a vigência atual
    if reajuste.sequencia_vigencia == ultima_vigencia:
        contrato.valor_global_reajustado = reajuste.valor_global_reajustado
    # Diferença de preço das competências já medidas (calculada antes de mexer nos preços das não medidas):
    # a positiva vira competência complementar; a negativa, crédito abatido nas próximas medições
    reajuste.diferenca_retroativa = diferenca_ate_aqui
    diferenca = gerar_competencia_diferenca(contrato, reajuste, novos)
    if reajuste.diferenca_retroativa < 0:
        registrar_credito_reajuste(sessao, contrato, reajuste, -reajuste.diferenca_retroativa)
    reajuste.situacao, reajuste.concluido_em = "concluido", agora_utc()
    contrato.versao += 1
    auditar(sessao, autor.login, "contrato.reajuste.concluir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"mes_referencia": reajuste.mes_referencia, "data_efeito": reajuste.efeito, "competencias_recalculadas": len(afetadas),
                   "competencia_diferenca": diferenca.identificador if diferenca else None,
                   "diferenca_retroativa": reajuste.diferenca_retroativa,
                   "campos": {"valor_global": {"de": reajuste.valor_global_atual, "para": reajuste.valor_global_reajustado}}})
    from app.services.contratos import avisos
    texto_aviso = (
        f"reajuste retroativo aplicado à {reajuste.sequencia_vigencia}ª vigência (até {reajuste.efeito - timedelta(days=1):%d/%m/%Y})"
        if reajuste.retroativo else f"reajuste aplicado a partir de {reajuste.efeito:%d/%m/%Y}"
    )
    avisos.alteracao_concluida(sessao, contrato, "reajuste", reajuste.id, texto_aviso, autor)
    sessao.commit()


def cancelar(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, autor: Usuario) -> None:
    """Cancela o reajuste em elaboração (nada muda no contrato)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    reajuste = _em_andamento(sessao, contrato, reajuste_id)
    reajuste.situacao, reajuste.cancelado_em = "cancelado", agora_utc()
    auditar(sessao, autor.login, "contrato.reajuste.cancelar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
    sessao.commit()


def arquivo(sessao: Session, contrato_id: uuid.UUID, reajuste_id: uuid.UUID, anexo_id: uuid.UUID):
    """Baixa um arquivo do reajuste; só aceita anexos que pertencem a ele."""
    contrato = obter_contrato(sessao, contrato_id)
    reajuste = next((r for r in _carregar(sessao, contrato) if r.id == reajuste_id), None)
    if reajuste is None:
        raise RegistroNaoEncontrado("Reajuste")
    permitidos = {reajuste.evidencia_anexo_id, reajuste.apostilamento_anexo_id} | {m.pdf_anexo_id for m in reajuste.memorias} | {m.xlsx_anexo_id for m in reajuste.memorias}
    if anexo_id not in permitidos:
        raise RegistroNaoEncontrado("Arquivo")
    return servico_anexos.resposta_download(sessao.get(Anexo, anexo_id))
