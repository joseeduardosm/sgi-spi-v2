# Criado por José Eduardo Santana Martins
# Este arquivo serve para descobrir o preço, a quantidade e o limite vigentes de cada item em cada mês.
"""Preço, quantidade e limite vigentes de cada item em cada mês, considerando o histórico.

- Preço: reajustes concluídos. Antes do primeiro reajuste vale o preço "atual" que ele fotografou;
  a partir do mês de referência, o preço reajustado.
- Quantidade mensal (contínuo): aditamentos/supressões concluídos, pela mesma lógica com o mês de efeito.
- Limite (sob demanda): linha de limite da vigência (prorrogação ou alteração); sem linha, o original.
- Executado: soma das medições concluídas da vigência.
"""

from datetime import date
from decimal import Decimal

from app.models.contratos import Contrato, ItemContrato
from app.services.contratos import calculos


def _reajustes(contrato: Contrato) -> list:
    return sorted((r for r in contrato.reajustes if r.situacao == "concluido"), key=lambda r: r.mes_referencia)


def _alteracoes(contrato: Contrato) -> list:
    return sorted((a for a in contrato.alteracoes if a.situacao == "concluida"), key=lambda a: a.mes_efeito)


def preco_em(contrato: Contrato, item: ItemContrato, competencia: date) -> Decimal:
    linhas = [(r.mes_referencia, linha) for r in _reajustes(contrato) for linha in r.itens if linha.item_id == item.id]
    if not linhas:
        return item.valor_unitario
    aplicadas = [linha for mes, linha in linhas if mes <= competencia]
    return aplicadas[-1].valor_unitario_reajustado if aplicadas else linhas[0][1].valor_unitario_atual


def quantidade_mensal_em(contrato: Contrato, item: ItemContrato, competencia: date) -> Decimal:
    linhas = [
        (a.mes_efeito, linha) for a in _alteracoes(contrato) for linha in a.itens if linha.item_id == item.id and linha.tipo == "continuo"
    ]
    if not linhas:
        return item.quantidade_mensal
    aplicadas = [linha for mes, linha in linhas if mes <= competencia]
    return aplicadas[-1].quantidade_nova if aplicadas else linhas[0][1].quantidade_original


def previsao_da_vigencia(contrato: Contrato, sequencia: int):
    return next((p for p in contrato.previsoes if p.sequencia_vigencia == sequencia), None)


def limite_na_vigencia(contrato: Contrato, item: ItemContrato, sequencia: int) -> Decimal:
    previsao = previsao_da_vigencia(contrato, sequencia)
    if previsao:
        for limite in previsao.limites:
            if limite.item_id == item.id:
                return limite.quantidade_total
    return item.quantidade_total


def executado_na_vigencia(contrato: Contrato, item: ItemContrato, sequencia: int, exceto=None) -> Decimal:
    """Quantidade medida (medições concluídas) do item na vigência. Competências de diferença de
    reajuste não contam: pagam só a diferença de preço sobre quantidades já executadas."""
    return sum(
        (
            linha.quantidade_medida
            for competencia in contrato.competencias
            if competencia.sequencia_vigencia == sequencia and competencia.medicao_concluida_em is not None
            and competencia.tipo == "regular" and competencia.id != exceto
            for linha in competencia.itens
            if linha.item_id == item.id
        ),
        Decimal(0),
    )


def valor_global_vigencia(
    contrato: Contrato, vigencia: calculos.Vigencia, precos_simulados: tuple[date, dict] | None = None
) -> Decimal:
    """Valor da vigência somado mês a mês, com o preço e a quantidade vigentes em cada mês.

    Contínuos: quantidade do mês × preço do mês × fator 30/360 (itens com pró-rata).
    Sob demanda: apontamentos da previsão × preço do mês, mais o saldo não apontado do limite
    ao preço do último mês. Assim, reajustes e aditamentos/supressões só afetam os meses a partir
    do efeito, e o valor coincide com a soma da previsão orçamentária.

    `precos_simulados` = (mês de referência, {item_id: novo preço}) simula um reajuste ainda em
    elaboração (memória de cálculo) sem gravar nada.
    """

    def preco(item: ItemContrato, mes: date) -> Decimal:
        if precos_simulados and mes >= precos_simulados[0] and item.id in precos_simulados[1]:
            return precos_simulados[1][item.id]
        return preco_em(contrato, item, mes)

    meses = calculos.meses_da_vigencia(vigencia)
    previsao = previsao_da_vigencia(contrato, vigencia.sequencia)
    apontados = {(a.item_id, a.competencia): a.quantidade for a in previsao.apontamentos} if previsao else {}
    total = Decimal(0)
    for item in contrato.itens:
        if item.tipo == "continuo":
            for mes in meses:
                fator = mes.fator if item.calcula_pro_rata else Decimal(1)
                total += quantidade_mensal_em(contrato, item, mes.competencia) * preco(item, mes.competencia) * fator
        else:
            apontado = Decimal(0)
            for mes in meses:
                quantidade = apontados.get((item.id, mes.competencia), Decimal(0))
                apontado += quantidade
                total += quantidade * preco(item, mes.competencia)
            saldo = limite_na_vigencia(contrato, item, vigencia.sequencia) - apontado
            if saldo > 0 and meses:
                total += saldo * preco(item, meses[-1].competencia)
    return calculos.arredondar(total)
