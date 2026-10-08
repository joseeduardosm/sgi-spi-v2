# Criado por José Eduardo Santana Martins
# Este arquivo serve para calcular o SLA de Tarefas e Melhorias (prazos de resposta e de resolução em dias úteis) e para manter a política.
"""SLA de prazos.

Para cada item, contam-se **dias úteis** (sem fins de semana e feriados do RH) a partir do **dia da criação**: o prazo de resposta é o primeiro
atendimento e o de resolução, a conclusão. A situação de cada marco é `cumprido` (feito até o último dia), `cumprido_fora` (feito depois),
ou, se ainda aberto, `no_prazo`, `em_risco` (80% ou mais do prazo consumido) ou `estourado` (passou do último dia).

Tarefas: política por prioridade; as geradas por outro módulo (controladas externamente) ficam fora. Melhorias: uma regra só; a resposta é a
primeira mudança de situação e a resolução, a conclusão ou a recusa. Sem linha ativa na tabela, valem os prazos padrão abaixo.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sla import SlaPolitica
from app.schemas.sla import GravacaoPoliticasSla, LeituraPoliticaSla, SlaItem
from app.services import calendario_util

FUSO = ZoneInfo("America/Sao_Paulo")
# 80% do prazo consumido já é "em risco"
LIMIAR_RISCO = 0.8
# Prazos padrão (dias úteis de resposta e de resolução), os mesmos gravados pela migração
PADROES: dict[tuple[str, str], tuple[int, int]] = {
    ("tarefas", "critica"): (1, 3), ("tarefas", "alta"): (2, 5), ("tarefas", "normal"): (3, 10), ("tarefas", "baixa"): (5, 20), ("melhorias", ""): (3, 15),
}


@dataclass(frozen=True)
class Contexto:
    """O que o cálculo precisa de fora: a política em vigor e os feriados (carregados uma vez por requisição)."""
    politicas: dict[tuple[str, str], tuple[int, int]]
    feriados: set[date]


def _com_fuso(momento: datetime) -> datetime:
    """Datas sempre com fuso (sem fuso, como o SQLite dos testes devolve, valem como UTC)."""
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=timezone.utc)


def _dia(momento: datetime) -> date:
    """Dia no horário de São Paulo."""
    return _com_fuso(momento).astimezone(FUSO).date()


def contexto(sessao: Session) -> Contexto:
    """Política e feriados, guardados na sessão para não consultar o banco a cada item da lista."""
    guardado = sessao.info.get("sla_contexto")
    if guardado is None:
        politicas = dict(PADROES)
        for linha in sessao.scalars(select(SlaPolitica).where(SlaPolitica.ativo.is_(True))):
            politicas[(linha.modulo, linha.prioridade)] = (linha.dias_uteis_resposta, linha.dias_uteis_resolucao)
        guardado = Contexto(politicas, calendario_util.feriados_cadastrados(sessao))
        sessao.info["sla_contexto"] = guardado
    return guardado


def _situacao(prazo: date, meta: int, criado: date, feito: datetime | None, hoje: date, feriados: set[date]) -> str:
    """Situação de um marco (resposta ou resolução)."""
    if feito is not None:
        return "cumprido" if _dia(feito) <= prazo else "cumprido_fora"
    if hoje > prazo:
        return "estourado"
    consumido = calendario_util.uteis_entre(criado, hoje, feriados)
    return "em_risco" if meta > 0 and consumido >= LIMIAR_RISCO * meta else "no_prazo"


def calcular(criado_em: datetime, respondido_em: datetime | None, resolvido_em: datetime | None, politica: tuple[int, int], feriados: set[date],
             hoje: date | None = None) -> SlaItem:
    """SLA de um item com as datas e a política dadas (função pura: testável sem banco)."""
    resposta, resolucao = politica
    hoje = hoje or datetime.now(FUSO).date()
    criado = _dia(criado_em)
    prazo_resposta = calendario_util.somar_uteis(criado, resposta, feriados)
    prazo_resolucao = calendario_util.somar_uteis(criado, resolucao, feriados)
    # Quem resolveu sem registrar o primeiro atendimento respondeu, no mínimo, ao resolver
    respondido = respondido_em or resolvido_em
    return SlaItem(
        meta_resposta_dias=resposta, meta_resolucao_dias=resolucao, prazo_resposta=prazo_resposta, prazo_resolucao=prazo_resolucao,
        respondido_em=respondido, resolvido_em=resolvido_em,
        situacao_resposta=_situacao(prazo_resposta, resposta, criado, respondido, hoje, feriados),
        situacao_resolucao=_situacao(prazo_resolucao, resolucao, criado, resolvido_em, hoje, feriados),
    )


def da_tarefa(sessao: Session, tarefa) -> SlaItem | None:
    """SLA da tarefa pela prioridade atual; `None` nas controladas por outro módulo (o ritmo delas é o do módulo de origem)."""
    if tarefa.controlada_externamente:
        return None
    ctx = contexto(sessao)
    politica = ctx.politicas.get(("tarefas", tarefa.prioridade)) or PADROES[("tarefas", "normal")]
    return calcular(tarefa.criado_em, tarefa.iniciada_em, tarefa.concluida_em, politica, ctx.feriados)


def da_sugestao(sessao: Session, sugestao) -> SlaItem:
    """SLA da sugestão de melhoria: resposta = primeira mudança de situação; resolução = conclusão ou recusa."""
    ctx = contexto(sessao)
    eventos = sorted((e for e in sugestao.eventos if e.situacao_anterior is not None), key=lambda e: _com_fuso(e.criado_em))
    respondido = eventos[0].criado_em if eventos else None
    resolvido = next((e.criado_em for e in eventos if e.situacao_nova in ("concluida", "recusada")), None)
    return calcular(sugestao.criado_em, respondido, resolvido, ctx.politicas[("melhorias", "")], ctx.feriados)


# ---------------------------------------------------------------------------------------------
# Política (tela de administração)
# ---------------------------------------------------------------------------------------------

def listar_politicas(sessao: Session) -> list[LeituraPoliticaSla]:
    """Todas as linhas da política (as ausentes na tabela aparecem com o prazo padrão), em ordem de módulo e gravidade."""
    gravadas = {(p.modulo, p.prioridade): p for p in sessao.scalars(select(SlaPolitica))}
    ordem = ["critica", "alta", "normal", "baixa", ""]
    linhas = []
    for (modulo, prioridade), (resposta, resolucao) in sorted(PADROES.items(), key=lambda x: (x[0][0], ordem.index(x[0][1]))):
        linha = gravadas.get((modulo, prioridade))
        linhas.append(LeituraPoliticaSla(modulo=modulo, prioridade=prioridade, ativo=linha.ativo if linha else True,
                                         dias_uteis_resposta=linha.dias_uteis_resposta if linha else resposta,
                                         dias_uteis_resolucao=linha.dias_uteis_resolucao if linha else resolucao))
    return linhas


def gravar_politicas(sessao: Session, dados: GravacaoPoliticasSla) -> list[LeituraPoliticaSla]:
    """Grava as linhas informadas (cria a que faltar); a resolução não pode ser menor que a resposta. Sem `commit` do contexto: quem chama decide."""
    from app.services.sla.erros import ErroSla

    gravadas = {(p.modulo, p.prioridade): p for p in sessao.scalars(select(SlaPolitica))}
    for nova in dados.politicas:
        if (nova.modulo, nova.prioridade) not in PADROES:
            raise ErroSla("Combinação de módulo e prioridade inválida.")
        if nova.dias_uteis_resolucao < nova.dias_uteis_resposta:
            raise ErroSla("O prazo de resolução não pode ser menor que o de resposta.")
        linha = gravadas.get((nova.modulo, nova.prioridade))
        if linha is None:
            linha = SlaPolitica(modulo=nova.modulo, prioridade=nova.prioridade, dias_uteis_resposta=0, dias_uteis_resolucao=0)
            sessao.add(linha)
        linha.dias_uteis_resposta, linha.dias_uteis_resolucao, linha.ativo = nova.dias_uteis_resposta, nova.dias_uteis_resolucao, nova.ativo
    sessao.flush()
    sessao.info.pop("sla_contexto", None)
    return listar_politicas(sessao)
