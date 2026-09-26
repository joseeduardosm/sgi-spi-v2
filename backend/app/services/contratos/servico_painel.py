# Criado por José Eduardo Santana Martins
# Este arquivo serve para montar o painel de contratos (pendências, alertas, execução orçamentária e números).
"""Painel executivo de contratos e exportação consolidada da previsão orçamentária.

O painel responde duas perguntas: "o que eu preciso fazer?" (pendências do usuário) e "onde está o
risco?" (alertas da carteira), com a execução orçamentária do exercício e os números da carteira.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.contratos import (
    AlteracaoQuantidade,
    AvaliacaoCompetencia,
    Competencia,
    Contrato,
    ProcessoProrrogacao,
    Reajuste,
)
from app.models.usuario import Usuario
from app.schemas.contratos.painel import AlertasContrato, ExecucaoOrcamentaria, MesExecucao, NumerosCarteira, OpcaoFiltro, Painel, Pendencia, Risco
from app.services.contratos import calculos
from app.services.contratos.servico_competencias import (
    CIENCIAS_MINIMAS,
    avaliacao_pronta_para_ciencia,
    ciencias_ateste,
    compromissos,
    etapas_abertas,
    requisitos,
    total_medido,
)
from app.services.contratos.servico_contratos import designacoes_vigentes, hoje, opcoes_carga_completa, situacao, totais
from app.services.contratos.servico_orcamento import meses_previstos
from app.services.contratos.servico_prorrogacao import meses_disponiveis
from app.services.contratos.servico_retencao import eh_financeiro

ZERO = Decimal(0)
# Nomes das etapas como aparecem nas pendências
ETAPAS_ROTULO = {
    "medicao": "Medição", "avaliacao": "Avaliação", "nota_fiscal": "Nota fiscal", "retencao": "Retenção de tributos", "cadin": "CADIN", "checklist": "Checklist",
    "consolidado": "Documento consolidado", "ordem_bancaria": "Ordem Bancária",
}
# Pagamento que vence em até 5 dias vira alerta de risco médio
DIAS_VENCENDO = 5
# Competência encerrada sem medição concluída vira risco depois deste prazo (e risco alto depois do dobro)
DIAS_ATRASO = 30


def carregar_contratos(sessao: Session) -> list[Contrato]:
    """Todos os contratos com o necessário para o painel (competências, ciências, avaliações e alterações)."""
    return list(
        sessao.scalars(
            select(Contrato).options(
                *opcoes_carga_completa(),
                selectinload(Contrato.competencias).selectinload(Competencia.ciencias),
                selectinload(Contrato.competencias).selectinload(Competencia.avaliacao),
                selectinload(Contrato.alteracoes).selectinload(AlteracaoQuantidade.ciencias),
            )
        )
    )


def _nome(competencia: Competencia) -> str:
    """"Competência 01/2027 · 1ª parte" ou "Diferença de reajuste 01/2026 a 04/2026"."""
    rotulo = competencia.numero_competencia
    return f"Competência {rotulo}" if competencia.tipo == "regular" else rotulo


def _medir_desde(competencia: Competencia) -> date:
    """Data a partir da qual a medição é esperada: o fim do período ou, na diferença de reajuste, a sua criação."""
    return competencia.periodo_fim if competencia.tipo == "regular" else competencia.criado_em.date()


def _rota_competencia(contrato: Contrato, competencia: Competencia) -> str:
    """Endereço (rota do Angular) da tela de execução da competência."""
    return f"/contratos/{contrato.id}/execucao/{competencia.identificador}"


def _pendencia(contrato: Contrato, tipo: str, descricao: str, rota: str, desde: date | None = None) -> Pendencia:
    """Monta uma pendência com os dados de identificação do contrato."""
    return Pendencia(tipo=tipo, contrato_id=contrato.id, contrato_numero=contrato.numero, contrato_apelido=contrato.apelido,
                     descricao=descricao, rota=rota, desde=desde)


def pendencias_do_usuario(sessao: Session, contratos: list[Contrato], usuario: Usuario) -> list[Pendencia]:
    """O que o usuário precisa fazer: só contratos em que ele é criador ou integrante vigente da equipe."""
    # Contratos com prorrogação e com reajuste em elaboração (uma consulta para cada)
    rascunhos_prorrogacao = set(sessao.scalars(select(ProcessoProrrogacao.contrato_id).where(ProcessoProrrogacao.situacao == "rascunho")))
    reajustes = set(sessao.scalars(select(Reajuste.contrato_id).where(Reajuste.situacao == "rascunho")))
    lista: list[Pendencia] = []
    referencia = hoje()
    # O Financeiro confere as retenções de todos os contratos, mesmo sem integrar a equipe
    financeiro = eh_financeiro(sessao, usuario)
    for contrato in contratos:
        membro = any(d.usuario_id == usuario.id for d in designacoes_vigentes(contrato))
        if not (membro or contrato.criador_id == usuario.id):
            if financeiro:
                for competencia in (c for c in contrato.competencias if c.etapa_atual == "retencao"):
                    lista.append(_pendencia(
                        contrato, "retencao", f"{_nome(competencia)}: conferir a retenção de tributos da NF {competencia.nf_numero}",
                        f"/contratos/{contrato.id}/execucao/{competencia.identificador}", competencia.nf_recebida_em or competencia.periodo_fim,
                    ))
            continue
        # Contrato ainda sem competências: a tarefa é completar a base e gerar a execução
        if not contrato.competencias and situacao(contrato) != "encerrado":
            faltas = requisitos(contrato).pendencias
            descricao = "Gerar as competências de execução" + (f" — falta: {faltas[0]}" if faltas else "")
            lista.append(_pendencia(contrato, "base_execucao", descricao, f"/contratos/{contrato.id}", contrato.data_inicio))
        # Competências já encerradas e não concluídas: cada uma gera uma pendência
        for competencia in contrato.competencias:
            if competencia.etapa_atual == "concluida" or referencia <= competencia.periodo_fim:
                continue
            rota = _rota_competencia(contrato, competencia)
            mes = _nome(competencia)
            etapa = competencia.etapa_atual
            # Na medição, enquanto falta a ciência mínima, a pendência de cada integrante é dar ciência;
            # depois dela (uma já basta), a pendência volta a ser a etapa (concluir a medição)
            if (etapa == "medicao" and membro and competencia.medicao_iniciada_em and len(competencia.ciencias) < CIENCIAS_MINIMAS
                    and not any(c.usuario_id == usuario.id for c in competencia.ciencias)):
                lista.append(_pendencia(contrato, "ciencia_medicao", f"{mes}: registrar sua ciência na medição", rota, competencia.periodo_fim))
                continue
            # Na avaliação, com as notas fechadas e sem nenhuma ciência no ateste (uma já basta),
            # a pendência de cada integrante da equipe é dar ciência
            avaliacao: AvaliacaoCompetencia | None = competencia.avaliacao
            if (etapa == "avaliacao" and membro and avaliacao and avaliacao_pronta_para_ciencia(avaliacao)
                    and len(ciencias_ateste(avaliacao)) < CIENCIAS_MINIMAS):
                lista.append(_pendencia(contrato, "ciencia_ateste", f"{mes}: registrar sua ciência no ateste da avaliação", rota, competencia.periodo_fim))
                continue
            # Nos demais casos, a pendência é a etapa atual (com o vencimento do pagamento, se já houver NF)
            vencimento = competencia.nf_recebida_em + timedelta(days=competencia.prazo_pagamento_dias) if competencia.nf_recebida_em and competencia.prazo_pagamento_dias else None
            prazo = f" · pagamento vence {vencimento:%d/%m/%Y}" if vencimento else ""
            # Depois da NF, retenção, CADIN e checklist correm em paralelo: uma pendência por etapa em aberto
            for aberta in etapas_abertas(competencia):
                sufixo = " (aguardando o Financeiro)" if aberta == "retencao" else ""
                lista.append(_pendencia(contrato, aberta, f"{mes}: {ETAPAS_ROTULO.get(aberta, aberta)}{sufixo}{prazo}", rota,
                                        vencimento or competencia.periodo_fim))
        # Atos em elaboração: prorrogação, reajuste e aditamento/supressão
        if contrato.id in rascunhos_prorrogacao:
            lista.append(_pendencia(contrato, "prorrogacao", "Prorrogação em elaboração", f"/contratos/{contrato.id}/prorrogacao", contrato.data_fim))
        if contrato.id in reajustes:
            lista.append(_pendencia(contrato, "reajuste", "Reajuste em elaboração", f"/contratos/{contrato.id}/reajuste"))
        for alteracao in contrato.alteracoes:
            if alteracao.situacao not in ("rascunho", "aguardando_ciencias"):
                continue
            nome = "Aditamento" if alteracao.tipo == "aditamento" else "Supressão"
            rota = f"/contratos/{contrato.id}/{alteracao.tipo}"
            # A pendência de ciência só existe enquanto ninguém deu a ciência mínima (uma já basta)
            if alteracao.situacao == "aguardando_ciencias" and membro and len(alteracao.ciencias) < CIENCIAS_MINIMAS:
                lista.append(_pendencia(contrato, "ciencia_alteracao", f"{nome}: registrar sua ciência", rota))
            else:
                lista.append(_pendencia(contrato, "alteracao", f"{nome} em elaboração", rota))
    # As mais urgentes (data mais antiga) primeiro
    return sorted(lista, key=lambda p: (p.desde or date.max, p.contrato_numero))


def alertas_da_carteira(sessao: Session, contratos: list[Contrato]) -> list[AlertasContrato]:
    """Riscos da carteira, agrupados por contrato: vigência, reajuste, empenho, pagamentos e atrasos."""
    rascunhos_prorrogacao = set(sessao.scalars(select(ProcessoProrrogacao.contrato_id).where(ProcessoProrrogacao.situacao == "rascunho")))
    referencia = hoje()
    grupos: list[AlertasContrato] = []
    for contrato in contratos:
        # Contratos encerrados ou suspensos não geram alertas
        estado = situacao(contrato)
        if estado in ("encerrado", "suspenso"):
            continue
        riscos: list[Risco] = []

        def risco(tipo, gravidade, descricao, rota, data=None, valor=None):
            """Acrescenta um risco à lista do contrato em análise."""
            riscos.append(Risco(tipo=tipo, gravidade=gravidade, descricao=descricao, rota=rota, data=data, valor=valor))

        # Vigência: perto do fim, sem prorrogação iniciada ou já sem prorrogação possível
        dias = (contrato.data_fim - referencia).days
        if estado == "a_vencer":
            if meses_disponiveis(contrato) <= 0:
                risco("vigencia_maxima", "alta", f"Vence em {dias} dia(s) e atingiu a vigência máxima: planejar nova contratação",
                      f"/contratos/{contrato.id}", contrato.data_fim)
            elif contrato.id not in rascunhos_prorrogacao:
                risco("a_vencer_sem_prorrogacao", "alta" if dias <= 60 else "media",
                      f"Vence em {dias} dia(s) e a prorrogação não foi iniciada", f"/contratos/{contrato.id}/prorrogacao", contrato.data_fim)
        # Reajuste: a partir de 12 meses de contrato, o mês de reajuste deste ano (ou do anterior) precisa ter reajuste aberto
        aniversario = calculos.somar_meses(contrato.data_inicio, 12)
        if referencia >= aniversario:
            mes_reajuste = date(referencia.year, contrato.mes_reajuste, 1)
            if mes_reajuste > referencia:
                mes_reajuste = date(referencia.year - 1, contrato.mes_reajuste, 1)
            if mes_reajuste >= calculos.primeiro_dia(aniversario) and not any(
                r.situacao != "cancelado" and r.mes_referencia >= mes_reajuste for r in contrato.reajustes
            ):
                risco("reajuste_pendente", "media", f"Mês de reajuste ({mes_reajuste:%m/%Y}) passou sem reajuste aberto",
                      f"/contratos/{contrato.id}/reajuste", mes_reajuste)

        # Empenho: o saldo livre (descontado o comprometido com medições a pagar) cobre a próxima competência a medir?
        reservado = compromissos(contrato)
        livre = sum((n.saldo - reservado.get(n.id, ZERO) for n in contrato.notas_empenho), ZERO)
        a_medir = sorted((c for c in contrato.competencias if c.medicao_concluida_em is None and c.tipo == "regular"), key=lambda c: c.periodo_inicio)
        if a_medir:
            proxima = a_medir[0]
            necessario = calculos.arredondar(sum((i.quantidade_prevista * i.valor_unitario for i in proxima.itens), ZERO))
            if livre < necessario:
                risco("empenho_insuficiente", "alta",
                      f"Saldo livre das NEs ({_moeda(livre)}) não cobre a competência {proxima.numero_competencia} ({_moeda(necessario)})",
                      f"/contratos/{contrato.id}", proxima.periodo_fim, necessario - livre)

        # Pagamentos: NFs com vencimento passado ou próximo
        abertas = [c for c in contrato.competencias if c.etapa_atual != "concluida"]
        for competencia in abertas:
            if competencia.nf_recebida_em and competencia.prazo_pagamento_dias:
                vencimento = competencia.nf_recebida_em + timedelta(days=competencia.prazo_pagamento_dias)
                if vencimento < referencia:
                    risco("pagamento_vencido", "alta", f"Pagamento da competência {competencia.numero_competencia} venceu em {vencimento:%d/%m/%Y}",
                          _rota_competencia(contrato, competencia), vencimento)
                elif (vencimento - referencia).days <= DIAS_VENCENDO:
                    risco("pagamento_vencendo", "media", f"Pagamento da competência {competencia.numero_competencia} vence em {vencimento:%d/%m/%Y}",
                          _rota_competencia(contrato, competencia), vencimento)

        # Atrasos: competências encerradas há mais de 30 dias sem medição concluída
        atrasadas = sorted(
            (c for c in abertas if c.medicao_concluida_em is None and (referencia - _medir_desde(c)).days > DIAS_ATRASO),
            key=_medir_desde,
        )
        if atrasadas:
            mais_antiga = atrasadas[0]
            atraso = (referencia - _medir_desde(mais_antiga)).days
            risco("competencias_atrasadas", "alta" if atraso > 2 * DIAS_ATRASO else "media",
                  f"{len(atrasadas)} competência(s) sem medição concluída há mais de {DIAS_ATRASO} dias "
                  f"(a mais antiga, {mais_antiga.numero_competencia}, há {atraso} dias)",
                  _rota_competencia(contrato, mais_antiga), mais_antiga.periodo_fim)

        # Riscos do contrato em ordem de gravidade e data; o contrato herda a gravidade do pior risco
        if riscos:
            ordem = {"alta": 0, "media": 1}
            riscos.sort(key=lambda r: (ordem[r.gravidade], r.data or date.max))
            grupos.append(
                AlertasContrato(
                    contrato_id=contrato.id, contrato_numero=contrato.numero, contrato_apelido=contrato.apelido,
                    empresa=contrato.empresa.razao_social, gravidade=riscos[0].gravidade, riscos=riscos,
                )
            )
    # Contratos com riscos altos primeiro; depois, os com mais riscos
    return sorted(grupos, key=lambda g: (0 if g.gravidade == "alta" else 1, -len(g.riscos), g.contrato_numero))


def _moeda(valor: Decimal) -> str:
    """Formata o valor em reais no padrão brasileiro (R$ 1.234,56)."""
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def execucao_orcamentaria(contratos: list[Contrato], exercicio: int) -> ExecucaoOrcamentaria:
    """Previsto × medido × pago por mês do exercício, e a situação dos empenhos."""
    # Acumuladores por mês (dia 1); `defaultdict(Decimal)` começa cada mês em zero
    previsto: dict[date, Decimal] = defaultdict(Decimal)
    medido: dict[date, Decimal] = defaultdict(Decimal)
    pago: dict[date, Decimal] = defaultdict(Decimal)
    for contrato in contratos:
        # Previsto: pela previsão orçamentária
        for mes in meses_previstos(contrato):
            if mes.competencia.year == exercicio:
                previsto[mes.competencia] += mes.valor
        # Medido: competências com medição concluída
        for competencia in contrato.competencias:
            if competencia.medicao_concluida_em and competencia.competencia.year == exercicio:
                medido[competencia.competencia] += total_medido(competencia)
        # Pago: débitos lançados nas NEs, no mês da COMPETÊNCIA paga (e não na data do pagamento):
        # a OB de agosto paga em setembro entra na barra de agosto. Estornos entram como negativos.
        mes_da_competencia = {c.id: c.competencia for c in contrato.competencias}
        for nota in contrato.notas_empenho:
            for movimento in nota.movimentos:
                mes = mes_da_competencia.get(movimento.competencia_id)
                if mes is not None and mes.year == exercicio:
                    pago[mes] += movimento.debito
    meses = [date(exercicio, m, 1) for m in range(1, 13)]
    empenhado = sum((n.valor_original for c in contratos for n in c.notas_empenho), ZERO)
    consumido = sum((n.consumido for c in contratos for n in c.notas_empenho), ZERO)
    return ExecucaoOrcamentaria(
        exercicio=exercicio,
        meses=[MesExecucao(competencia=m, previsto=previsto[m], medido=medido[m], pago=pago[m]) for m in meses],
        total_previsto=sum(previsto.values(), ZERO), total_medido=sum(medido.values(), ZERO), total_pago=sum(pago.values(), ZERO),
        empenhado=empenhado, consumido=consumido, saldo_empenho=empenhado - consumido,
    )


def numeros(contratos: list[Contrato]) -> NumerosCarteira:
    """Contagens e somas da carteira (ativos inclui os "a vencer")."""
    estados = {c.id: situacao(c) for c in contratos}
    ativos = [c for c in contratos if estados[c.id] in ("ativo", "a_vencer")]
    valores_totais = [totais(c) for c in ativos]
    return NumerosCarteira(
        contratos_ativos=len(ativos), contratos_a_vencer=sum(1 for c in contratos if estados[c.id] == "a_vencer"),
        contratos_encerrados=sum(1 for c in contratos if estados[c.id] == "encerrado"),
        valor_global_ativos=sum((v for _, v in valores_totais), ZERO), base_mensal_ativos=sum((b for b, _ in valores_totais), ZERO),
    )


def montar_painel(sessao: Session, usuario: Usuario, exercicio: int | None, empresa_id: uuid.UUID | None, contrato_id: uuid.UUID | None) -> Painel:
    """Monta o painel inteiro. Os filtros valem para alertas, execução e números, não para as pendências."""
    todos = carregar_contratos(sessao)
    filtrados = [c for c in todos if (empresa_id is None or c.empresa_id == empresa_id) and (contrato_id is None or c.id == contrato_id)]
    # Opções de empresa do filtro, sem repetição
    empresas = {c.empresa.id: c.empresa.razao_social for c in todos}
    return Painel(
        hoje=hoje(),
        minhas_pendencias=pendencias_do_usuario(sessao, todos, usuario),
        alertas=alertas_da_carteira(sessao, filtrados),
        execucao=execucao_orcamentaria(filtrados, exercicio or hoje().year),
        numeros=numeros(filtrados),
        empresas=[OpcaoFiltro(id=i, rotulo=n) for i, n in sorted(empresas.items(), key=lambda e: e[1].lower())],
        contratos=[OpcaoFiltro(id=c.id, rotulo=f"{c.numero} · {c.apelido or c.empresa.razao_social}")
                   for c in sorted(todos, key=lambda c: (-c.ano, -c.sequencial))],
    )

