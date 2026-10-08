# Criado por José Eduardo Santana Martins
# Este arquivo serve para descobrir o preço, a quantidade e o limite vigentes de cada item em cada mês.
"""Preço, quantidade e limite vigentes de cada item em cada mês, considerando o histórico.

- Preço: reajustes concluídos. Antes do primeiro reajuste vale o preço "atual" que ele fotografou;
  a partir da **data de efeito** do reajuste (qualquer dia da vigência), o preço reajustado.
- Mês com virada (prorrogação ou reajuste no meio do mês): o mês é cortado em **trechos** (`trechos_do_mes`), cada um com o seu
  preço e pago pelos seus dias (fator 30/360, todos os itens).
- Quantidade mensal (contínuo): aditamentos/supressões concluídos, pela mesma lógica com o mês de efeito.
- Limite (sob demanda): linha de limite da vigência (prorrogação ou alteração); sem linha, o original.
- Executado: soma das medições concluídas da vigência.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.models.contratos import Contrato, ItemContrato
from app.services.contratos import calculos


def _reajustes(contrato: Contrato) -> list:
    """Reajustes concluídos, do mais antigo para o mais recente (pela data de efeito)."""
    return sorted((r for r in contrato.reajustes if r.situacao == "concluido"), key=lambda r: r.efeito)


def _alteracoes(contrato: Contrato) -> list:
    """Aditamentos/supressões concluídos, do mais antigo para o mais recente."""
    return sorted((a for a in contrato.alteracoes if a.situacao == "concluida"), key=lambda a: a.mes_efeito)


def preco_em(contrato: Contrato, item: ItemContrato, quando: date) -> Decimal:
    """Preço unitário do item válido na data informada (quem passa o dia 1 de um mês pega o preço do começo do mês)."""
    # Todas as linhas deste item em reajustes concluídos, com a data a partir da qual valem
    linhas = [(r.efeito, linha) for r in _reajustes(contrato) for linha in r.itens if linha.item_id == item.id]
    # Nunca foi reajustado: vale o preço do cadastro
    if not linhas:
        return item.valor_unitario
    # O último reajuste já em vigor na data; se nenhum ainda vigorava, o preço anterior ao 1º
    aplicadas = [linha for dia, linha in linhas if dia <= quando]
    return aplicadas[-1].valor_unitario_reajustado if aplicadas else linhas[0][1].valor_unitario_atual


@dataclass(frozen=True)
class Trecho:
    """Parte de um mês com um único preço e uma única vigência."""

    competencia: date  # dia 1 do mês
    inicio: date
    fim: date
    sequencia_vigencia: int

    @property
    def fator(self) -> Decimal:
        """Fração do mês pelos dias comerciais (30/360): 19 dias = 19/30."""
        return calculos.PeriodoMensal(self.competencia, self.inicio, self.fim, self.sequencia_vigencia).fator


def datas_de_efeito(contrato: Contrato) -> list[date]:
    """Datas a partir das quais os reajustes concluídos mudam os preços."""
    return sorted({r.efeito for r in _reajustes(contrato)})


def cortar_em_trechos(parte: calculos.PeriodoMensal, cortes: list[date]) -> list[Trecho]:
    """Divide a parte do mês (coberta por uma vigência) nas datas de corte que caem depois do primeiro dia dela."""
    pontos = sorted({c for c in cortes if parte.inicio < c <= parte.fim})
    limites = [parte.inicio, *pontos]
    return [
        Trecho(parte.competencia, inicio, (limites[n + 1] - timedelta(days=1)) if n + 1 < len(limites) else parte.fim, parte.sequencia_vigencia)
        for n, inicio in enumerate(limites)
    ]


def trechos_do_mes(contrato: Contrato, mes: date) -> list[Trecho]:
    """Trechos do mês civil `mes` (dia 1), cortados pelas viradas de vigência e pelas datas de efeito de reajuste."""
    from app.services.contratos.servico_contratos import vigencias

    partes = [p for v in vigencias(contrato) for p in calculos.meses_da_vigencia(v) if p.competencia == mes]
    cortes = datas_de_efeito(contrato)
    return [t for p in partes for t in cortar_em_trechos(p, cortes)]


@dataclass(frozen=True)
class TrechoCompetencia:
    """Trecho de uma competência: dias seguidos com a mesma vigência e o mesmo preço (pode juntar vários meses)."""

    inicio: date
    fim: date
    sequencia_vigencia: int
    partes: tuple[Trecho, ...]  # as partes mensais que o formam


def trechos_da_competencia(contrato: Contrato, periodo: calculos.PeriodoExecucao) -> list[TrechoCompetencia]:
    """Trechos de uma competência: cada parte mensal cortada nas datas de efeito de reajuste e juntas as vizinhas sem virada.

    Uma virada é a mudança de vigência ou uma data de efeito de reajuste. Sem virada, a competência tem um trecho só; com ela, o
    item é medido uma vez por trecho.
    """
    cortes = datas_de_efeito(contrato)
    partes = [t for p in periodo.meses for t in cortar_em_trechos(p, cortes)]
    grupos: list[list[Trecho]] = []
    for parte in partes:
        anterior = grupos[-1][-1] if grupos else None
        virou = anterior is not None and (anterior.sequencia_vigencia != parte.sequencia_vigencia or any(anterior.fim < c <= parte.inicio for c in cortes))
        if anterior is None or virou:
            grupos.append([parte])
        else:
            grupos[-1].append(parte)
    return [TrechoCompetencia(g[0].inicio, g[-1].fim, g[0].sequencia_vigencia, tuple(g)) for g in grupos]


def quantidade_mensal_em(contrato: Contrato, item: ItemContrato, competencia: date) -> Decimal:
    """Quantidade mensal do item contínuo válida na competência (mesma lógica do preço)."""
    linhas = [
        (a.mes_efeito, linha) for a in _alteracoes(contrato) for linha in a.itens if linha.item_id == item.id and linha.tipo == "continuo"
    ]
    if not linhas:
        return item.quantidade_mensal
    aplicadas = [linha for mes, linha in linhas if mes <= competencia]
    return aplicadas[-1].quantidade_nova if aplicadas else linhas[0][1].quantidade_original


def previsao_da_vigencia(contrato: Contrato, sequencia: int):
    """Previsão orçamentária da vigência `sequencia`, se existir."""
    return next((p for p in contrato.previsoes if p.sequencia_vigencia == sequencia), None)


def limite_na_vigencia(contrato: Contrato, item: ItemContrato, sequencia: int) -> Decimal:
    """Teto do item sob demanda na vigência (definido na prorrogação ou na alteração)."""
    previsao = previsao_da_vigencia(contrato, sequencia)
    if previsao:
        for limite in previsao.limites:
            if limite.item_id == item.id:
                return limite.quantidade_total
    # Sem limite específico: vale a quantidade total do cadastro
    return item.quantidade_total


def executado_na_vigencia(contrato: Contrato, item: ItemContrato, sequencia: int, exceto=None) -> Decimal:
    """Quantidade medida (medições concluídas) do item na vigência. Competências de diferença de
    reajuste não contam: pagam só a diferença de preço sobre quantidades já executadas.

    Cada linha da medição vale na sua vigência (`sequencia_vigencia` do trecho; sem ela, a da competência)."""
    # `exceto` permite ignorar uma competência (ex.: a que está sendo medida agora)
    return sum(
        (
            linha.quantidade_medida
            for competencia in contrato.competencias
            if competencia.medicao_concluida_em is not None and competencia.tipo in ("regular", "adicional") and competencia.id != exceto
            for linha in competencia.itens
            if linha.item_id == item.id and (linha.sequencia_vigencia or competencia.sequencia_vigencia) == sequencia
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

    def preco(item: ItemContrato, quando: date) -> Decimal:
        """Preço na data: o simulado (se houver para o item e já em vigor na data) ou o vigente."""
        if precos_simulados and quando >= precos_simulados[0] and item.id in precos_simulados[1]:
            return precos_simulados[1][item.id]
        return preco_em(contrato, item, quando)

    # Apontamentos da previsão indexados por (item, mês), para consulta rápida
    meses = calculos.meses_da_vigencia(vigencia)
    previsao = previsao_da_vigencia(contrato, vigencia.sequencia)
    apontados = {(a.item_id, a.competencia): a.quantidade for a in previsao.apontamentos} if previsao else {}
    # Trechos de cada mês nesta vigência (e se o mês foi dividido por virada de vigência ou de preço)
    por_mes = {}
    for mes in meses:
        todos = trechos_do_mes(contrato, mes.competencia)
        por_mes[mes.competencia] = ([t for t in todos if t.sequencia_vigencia == vigencia.sequencia], len(todos) > 1)
    total = Decimal(0)
    for item in contrato.itens:
        # Item contínuo: soma mês a mês (pró-rata nos meses parciais se o item usar; mês dividido: todos os itens pelos dias)
        if item.tipo == "continuo":
            for mes in meses:
                trechos, dividido = por_mes[mes.competencia]
                quantidade = quantidade_mensal_em(contrato, item, mes.competencia)
                for trecho in trechos:
                    fator = trecho.fator if dividido else (mes.fator if item.calcula_pro_rata else Decimal(1))
                    total += quantidade * preco(item, trecho.inicio) * fator
        else:
            # Item sob demanda: soma os apontamentos (repartidos pelos dias quando o mês tem mais de um preço na vigência)
            # e completa com o saldo que não foi apontado
            apontado = Decimal(0)
            for mes in meses:
                trechos, _ = por_mes[mes.competencia]
                quantidade = apontados.get((item.id, mes.competencia), Decimal(0))
                apontado += quantidade
                soma_fatores = sum((t.fator for t in trechos), Decimal(0)) or Decimal(1)
                for trecho in trechos:
                    total += quantidade * (trecho.fator / soma_fatores) * preco(item, trecho.inicio)
            saldo = limite_na_vigencia(contrato, item, vigencia.sequencia) - apontado
            ultimos = por_mes[meses[-1].competencia][0] if meses else []
            if saldo > 0 and ultimos:
                total += saldo * preco(item, ultimos[-1].inicio)
    return calculos.arredondar(total)
