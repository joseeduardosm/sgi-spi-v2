# Criado por José Eduardo Santana Martins
# Este arquivo serve para calcular os dados de cada slide do Painel Executivo, reaproveitando os serviços dos módulos.
"""Slides: contratos, RH e tarefas. Visão da organização inteira, sem o escopo pessoal de cada módulo."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.rh import Afastamento
from app.models.tarefas import EquipeTarefas, Tarefa
from app.models.usuario import Usuario
from app.schemas.painel_executivo import (
    AlertaSetorResumo, EquipeResumo, FaixaVencimento, FeriasVencendo, MesAfastamentos, PessoaAfastada, PontoAcumulado, RiscoResumo, SemanaTarefas,
    SetorAfastamentos, SlideContratos, SlideRh, SlideTarefas,
)
from app.services.contratos import servico_painel
from app.services.contratos.servico_contratos import hoje as hoje_contratos
from app.services.rh import servico_afastamentos, servico_periodos
from app.services.rh.papeis import setor_do_usuario
from app.services.tarefas import servico_tarefas

ZERO = Decimal("0.00")
SEMANAS = 12


# ---------------------------------------------------------------------------------------------
# Contratos
# ---------------------------------------------------------------------------------------------

def contratos(sessao: Session, exercicio: int | None) -> SlideContratos:
    """Execução do exercício (previsto × medido × pago, acumulado), vencimentos e os 5 contratos de maior risco."""
    todos = servico_painel.carregar_contratos(sessao)
    ano = exercicio or hoje_contratos().year
    execucao = servico_painel.execucao_orcamentaria(todos, ano)
    pontos, previsto, medido, pago = [], ZERO, ZERO, ZERO
    for mes in execucao.meses:
        previsto, medido, pago = previsto + mes.previsto, medido + mes.medido, pago + mes.pago
        pontos.append(PontoAcumulado(competencia=mes.competencia, previsto=previsto, medido=medido, pago=pago))
    vigentes = servico_painel.vigencias_da_carteira(sessao, None).contratos
    vencimentos = [FaixaVencimento(ate_dias=d, contratos=sum(1 for c in vigentes if 0 <= c.dias_restantes <= d)) for d in (30, 60, 90)]
    alertas = servico_painel.alertas_da_carteira(sessao, todos)
    # Mais graves primeiro; entre iguais, quem tem mais riscos
    ordenados = sorted(alertas, key=lambda a: (a.gravidade != "alta", -len(a.riscos), a.contrato_numero))
    return SlideContratos(
        gerado_em=agora_utc(), exercicio=ano, numeros=servico_painel.numeros(todos), execucao=execucao, acumulado=pontos, vencimentos=vencimentos,
        alertas_altos=sum(1 for a in alertas if a.gravidade == "alta"), alertas_medios=sum(1 for a in alertas if a.gravidade == "media"),
        maiores_riscos=[RiscoResumo(
            contrato_numero=a.contrato_numero, contrato_apelido=a.contrato_apelido, empresa=a.empresa, gravidade=a.gravidade, riscos=len(a.riscos),
            principal=(next((r for r in a.riscos if r.gravidade == "alta"), a.riscos[0])).descricao,
            rota=(next((r for r in a.riscos if r.gravidade == "alta"), a.riscos[0])).rota) for a in ordenados[:5]],
    )


# ---------------------------------------------------------------------------------------------
# RH
# ---------------------------------------------------------------------------------------------

def _dias_no_ano(a: Afastamento, ano: int) -> int:
    inicio, fim = max(a.inicio, date(ano, 1, 1)), min(a.fim, date(ano, 12, 31))
    return max(0, (fim - inicio).days + 1)


def rh(sessao: Session, ano: int | None) -> SlideRh:
    """Quem está fora hoje, afastamentos por mês e por setor, férias a vencer e setores acima do limite."""
    hoje = servico_afastamentos.hoje()
    ano = ano or hoje.year
    inicio_ano, fim_ano = date(ano, 1, 1), date(ano, 12, 31)
    periodos = list(sessao.scalars(select(Afastamento).where(
        Afastamento.status.in_(("aprovado", "gozado")), Afastamento.inicio <= fim_ano, Afastamento.fim >= inicio_ano).order_by(Afastamento.inicio)))
    usuarios = {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_({a.usuario_id for a in periodos})))} if periodos else {}

    hoje_fora = [PessoaAfastada(nome=usuarios[a.usuario_id].nome_completo or usuarios[a.usuario_id].login, setor=setor_do_usuario(usuarios[a.usuario_id]),
                                tipo=a.tipo, fim=a.fim)
                 for a in periodos if a.inicio <= hoje <= a.fim and a.usuario_id in usuarios]

    por_mes = []
    for mes in range(1, 13):
        ini = date(ano, mes, 1)
        fim = (date(ano + (mes == 12), mes % 12 + 1, 1)) - timedelta(days=1)
        ativos = [a for a in periodos if a.inicio <= fim and a.fim >= ini]
        por_mes.append(MesAfastamentos(
            mes=mes, ferias=len({a.usuario_id for a in ativos if a.tipo == "ferias"}),
            licenca_premio=len({a.usuario_id for a in ativos if a.tipo == "licenca_premio"})))

    dias: dict[str, int] = defaultdict(int)
    pessoas: dict[str, set[int]] = defaultdict(set)
    for a in periodos:
        if a.usuario_id in usuarios:
            setor = setor_do_usuario(usuarios[a.usuario_id])
            dias[setor] += _dias_no_ano(a, ano)
            pessoas[setor].add(a.usuario_id)
    por_setor = sorted((SetorAfastamentos(setor=s, dias=d, pessoas=len(pessoas[s])) for s, d in dias.items()), key=lambda x: -x.dias)[:8]

    a_vencer = servico_periodos.a_vencer(sessao, None, hoje)
    sessao.commit()
    alertas = servico_afastamentos.alertas_setor(sessao, [a for a in periodos if a.fim >= hoje], usuarios, hoje, min(fim_ano, hoje + timedelta(days=90)))
    return SlideRh(
        gerado_em=agora_utc(), ano=ano, afastados_hoje=sorted(hoje_fora, key=lambda p: p.nome), por_mes=por_mes, por_setor=por_setor,
        ferias_a_vencer=[FeriasVencendo(nome=u.nome_completo or u.login, setor=setor_do_usuario(u), disponivel=s.disponivel, periodo_fim=s.periodo.fim)
                         for u, s in a_vencer][:8],
        alertas_setor=[AlertaSetorResumo(**x) for x in alertas[:6]],
    )


# ---------------------------------------------------------------------------------------------
# Tarefas
# ---------------------------------------------------------------------------------------------

def _segunda(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def tarefas(sessao: Session) -> SlideTarefas:
    """Totais da organização, situação por equipe e criadas × concluídas nas últimas 12 semanas."""
    agora = agora_utc()
    todas = list(sessao.scalars(select(Tarefa).where(Tarefa.tarefa_pai_id.is_(None))))
    geral = servico_tarefas.indicadores(todas, agora)
    equipes = []
    for equipe in sessao.scalars(select(EquipeTarefas).where(EquipeTarefas.ativa.is_(True)).order_by(EquipeTarefas.nome)):
        da_equipe = [t for t in todas if t.equipe_id == equipe.id]
        if not da_equipe:
            continue
        ind = servico_tarefas.indicadores(da_equipe, agora)
        equipes.append(EquipeResumo(equipe=equipe.nome, abertas=ind["operacionais"], atrasadas=ind["atrasadas"], criticas=ind["criticas"],
                                    carga=ind["carga"], faixa=ind["faixa"]))
    equipes.sort(key=lambda e: (-e.atrasadas, -e.abertas, e.equipe))

    primeira = _segunda(agora.date()) - timedelta(weeks=SEMANAS - 1)
    criadas: dict[date, int] = defaultdict(int)
    concluidas: dict[date, int] = defaultdict(int)
    for t in todas:
        if t.criado_em and _segunda(_naive(t.criado_em).date()) >= primeira:
            criadas[_segunda(_naive(t.criado_em).date())] += 1
        if t.concluida_em and _segunda(_naive(t.concluida_em).date()) >= primeira:
            concluidas[_segunda(_naive(t.concluida_em).date())] += 1
    semanas = [SemanaTarefas(inicio=primeira + timedelta(weeks=i), criadas=criadas[primeira + timedelta(weeks=i)],
                             concluidas=concluidas[primeira + timedelta(weeks=i)]) for i in range(SEMANAS)]
    limite = agora - timedelta(days=30)
    return SlideTarefas(
        gerado_em=agora, abertas=geral["operacionais"], atrasadas=geral["atrasadas"], vencem_hoje=geral["vencem_hoje"], criticas=geral["criticas"],
        em_validacao=geral["em_validacao"], concluidas_30_dias=sum(1 for t in todas if t.concluida_em and _naive(t.concluida_em) >= _naive(limite)),
        equipes=equipes[:10], semanas=semanas,
    )


def _naive(valor: datetime) -> datetime:
    """Data/hora sem fuso (o SQLite dos testes devolve sem fuso; o PostgreSQL, com UTC)."""
    return valor.replace(tzinfo=None) if valor.tzinfo else valor
