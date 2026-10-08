# Criado por José Eduardo Santana Martins
# Este arquivo serve para calcular o desempenho de uma equipe de tarefas: burndown, vazão, tempo de ciclo, fluxo acumulado e produtividade por pessoa.
"""Desempenho da equipe (visão da liderança).

O histórico não tem tabela própria: é **reconstruído** de `criado_em` e dos eventos de status da linha do tempo (`dados.de/para`). Tarefas
migradas, cujos eventos não têm `de/para`, usam os carimbos da própria tarefa (`iniciada_em`, `entregue_em`, `concluida_em`). Entram as tarefas da
equipe e das sub-equipes (só as tarefas, sem contar as subtarefas); tarefas excluídas não existem mais e ficam de fora.

- **Burndown** (contagem de tarefas): abertas ao fim de cada dia, linha ideal (do total do início do período até zero no último dia) e linha de
  escopo (tudo o que estava no escopo até o dia, mostra o que entrou no meio do período). Dias futuros ficam sem valor.
- **Vazão**: por semana (segunda a domingo), tarefas criadas e concluídas e a média móvel de 4 semanas das concluídas.
- **Ciclo e lead time**: por semana de conclusão, mediana e percentil 85, em dias (ciclo = primeira vez em andamento → conclusão;
  lead time = criação → conclusão).
- **Fluxo acumulado**: por dia, quantas tarefas em cada situação.
- **Por pessoa**: concluídas no período e lead time médio de cada responsável.
"""

import math
import statistics
import uuid
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import hoje_sao_paulo
from app.models.tarefas import EquipeTarefas, EventoTarefa, STATUS_TAREFA, Tarefa
from app.services.tarefas import servico_tarefas as servico
from app.services.tarefas.servico_tarefas import ErroTarefa

FUSO = ZoneInfo("America/Sao_Paulo")
PERIODO_MAXIMO_DIAS = 366
TIPOS_STATUS = ("status", "entregue", "validada", "devolvida", "reaberta")


@dataclass
class Historico:
    """Linha do tempo de situações de uma tarefa: instantes (UTC, em ordem) e a situação que começa em cada um."""
    tarefa: Tarefa
    instantes: list[datetime] = field(default_factory=list)
    situacoes: list[str] = field(default_factory=list)

    def situacao_em(self, instante: datetime) -> str | None:
        """Situação no instante (None se a tarefa ainda não existia)."""
        i = bisect_right(self.instantes, instante)
        return self.situacoes[i - 1] if i else None

    def conclusoes(self) -> list[datetime]:
        """Conclusões que valem hoje: só a vigente, e só se a tarefa está concluída agora.

        Uma conclusão desfeita (a tarefa foi reaberta) não conta em vazão, ciclo, lead time nem por pessoa; reaberta e concluída de novo
        conta uma vez, na data da última conclusão. Assim os números refletem o estado real das tarefas."""
        if not self.situacoes or self.situacoes[-1] != "concluida":
            return []
        return [self.instantes[-1]]

    def primeiro_inicio(self) -> datetime | None:
        return next((t for t, s in zip(self.instantes, self.situacoes, strict=True) if s == "em_andamento"), None)


def _utc(valor: datetime) -> datetime:
    return servico._comparavel(valor).astimezone(timezone.utc)


def _fim_do_dia(dia: date) -> datetime:
    return datetime.combine(dia, time.max, tzinfo=FUSO).astimezone(timezone.utc)


def reconstruir(tarefa: Tarefa, eventos: list[EventoTarefa]) -> Historico:
    """Histórico de situações a partir dos eventos de status; sem `de/para` (migradas), usa os carimbos da tarefa."""
    h = Historico(tarefa)
    marcos: list[tuple[datetime, str]] = [(_utc(tarefa.criado_em), "a_fazer")]
    do_evento = [(_utc(e.criado_em), (e.dados or {}).get("para")) for e in eventos if e.tipo in TIPOS_STATUS]
    do_evento = [(t, p) for t, p in do_evento if p in STATUS_TAREFA]
    if do_evento:
        marcos += do_evento
    else:
        for carimbo, situacao in ((tarefa.iniciada_em, "em_andamento"), (tarefa.entregue_em, "em_validacao"), (tarefa.concluida_em, "concluida")):
            if carimbo is not None:
                marcos.append((_utc(carimbo), situacao))
    marcos.sort(key=lambda m: m[0])
    # Se o final reconstruído não bate com a situação atual (histórico incompleto), a situação atual vale a partir da última atualização
    if marcos[-1][1] != tarefa.status:
        quando = tarefa.concluida_em if tarefa.status == "concluida" and tarefa.concluida_em else tarefa.atualizado_em
        marcos.append((max(_utc(quando), marcos[-1][0]), tarefa.status))
    h.instantes = [t for t, _ in marcos]
    h.situacoes = [s for _, s in marcos]
    return h


def _percentil(valores: list[float], p: float) -> float | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    return round(ordenados[max(0, math.ceil(p * len(ordenados)) - 1)], 1)


def _mediana(valores: list[float]) -> float | None:
    return round(statistics.median(valores), 1) if valores else None


def _dias(inicio: datetime, fim: datetime) -> float:
    return max(0.0, (fim - inicio).total_seconds() / 86400)


def _segunda(d: date) -> date:
    return d - timedelta(days=d.weekday())


def calcular(sessao: Session, usuario, equipe_id: uuid.UUID, de: date, ate: date, marcador_id: uuid.UUID | None = None) -> dict:
    """Desempenho da equipe no período (só dono, líderes e SuperRoot)."""
    equipe = sessao.get(EquipeTarefas, equipe_id)
    if equipe is None:
        raise ErroTarefa("Equipe não encontrada.", 404, "nao_encontrado")
    if not (usuario.superusuario or usuario.id in servico.lideranca(sessao, equipe)):
        raise ErroTarefa("Só a liderança da equipe vê o desempenho.", 403, "sem_permissao")
    _validar_periodo(de, ate)
    ids_equipes = [e.id for e in servico._com_subequipes(sessao, equipe)]
    tarefas = list(sessao.scalars(select(Tarefa).where(Tarefa.equipe_id.in_(ids_equipes), Tarefa.tarefa_pai_id.is_(None))))
    return _metricas(sessao, tarefas, de, ate, marcador_id, equipe.id, equipe.nome)


def _validar_periodo(de: date, ate: date) -> None:
    if ate < de:
        raise ErroTarefa("O início do período é depois do fim.")
    if (ate - de).days >= PERIODO_MAXIMO_DIAS:
        raise ErroTarefa(f"O período pode ter no máximo {PERIODO_MAXIMO_DIAS} dias.")


def calcular_pessoa(sessao: Session, usuario, pessoa, de: date, ate: date, marcador_id: uuid.UUID | None = None) -> dict:
    """Desempenho de uma pessoa: as tarefas em que ela é responsável, de qualquer equipe e também as pessoais (sem equipe).

    Quem vê: a própria pessoa (tudo), o SuperRoot (tudo) e a liderança (só as tarefas das equipes que lidera; as pessoais não)."""
    _validar_periodo(de, ate)
    tarefas = [t for t in servico.da_pessoa(sessao, usuario, pessoa) if t.tarefa_pai_id is None and pessoa.id in servico.envolvidos(t)]
    resultado = _metricas(sessao, tarefas, de, ate, marcador_id, None, pessoa.nome_completo or pessoa.login)
    resultado["escopo"] = "pessoa"
    return resultado


def _percentual(dentro: int, fora: int) -> float | None:
    return round(100 * dentro / (dentro + fora), 1) if dentro + fora else None


def _sla_do_periodo(sessao: Session, historicos: list[Historico], inicio: datetime, fim: datetime) -> tuple[dict, dict[int, float | None]]:
    """Cumprimento do SLA: resoluções e primeiros atendimentos feitos no período e abertas com prazo vencido ou em risco (só tarefas com SLA)."""
    from app.services.sla import servico_sla

    resolucao = [0, 0]  # no prazo, fora
    resposta = [0, 0]
    estouradas = em_risco = 0
    por_pessoa: dict[int, list[int]] = {}
    for h in historicos:
        item = servico_sla.da_tarefa(sessao, h.tarefa)
        if item is None:
            continue
        if item.resolvido_em is not None and inicio < _utc(item.resolvido_em) <= fim:
            no_prazo = item.situacao_resolucao == "cumprido"
            resolucao[0 if no_prazo else 1] += 1
            for r in h.tarefa.responsaveis:
                por_pessoa.setdefault(r.usuario_id, [0, 0])[0 if no_prazo else 1] += 1
        if item.respondido_em is not None and inicio < _utc(item.respondido_em) <= fim:
            resposta[0 if item.situacao_resposta == "cumprido" else 1] += 1
        if h.tarefa.status != "concluida":
            estouradas += item.situacao_resolucao == "estourado"
            em_risco += item.situacao_resolucao == "em_risco"
    resumo = {
        "resolucoes_no_prazo": resolucao[0], "resolucoes_fora": resolucao[1], "percentual_resolucao": _percentual(*resolucao),
        "respostas_no_prazo": resposta[0], "respostas_fora": resposta[1], "percentual_resposta": _percentual(*resposta),
        "abertas_estouradas": estouradas, "abertas_em_risco": em_risco,
    }
    return resumo, {uid: _percentual(d, f) for uid, (d, f) in por_pessoa.items()}


def _metricas(sessao: Session, tarefas: list[Tarefa], de: date, ate: date, marcador_id: uuid.UUID | None, equipe_id: uuid.UUID | None, titulo: str) -> dict:
    """Burndown, vazão, ciclo, fluxo e pessoas de um conjunto de tarefas no período (usado pela equipe e pela pessoa)."""
    if marcador_id is not None:
        tarefas = [t for t in tarefas if any(m.id == marcador_id for m in t.marcadores)]
    eventos: dict[uuid.UUID, list[EventoTarefa]] = {}
    if tarefas:
        for e in sessao.scalars(select(EventoTarefa).where(EventoTarefa.tarefa_id.in_([t.id for t in tarefas]), EventoTarefa.tipo.in_(TIPOS_STATUS))):
            eventos.setdefault(e.tarefa_id, []).append(e)
    historicos = [reconstruir(t, eventos.get(t.id, [])) for t in tarefas]

    hoje = hoje_sao_paulo()
    dias = [de + timedelta(days=i) for i in range((ate - de).days + 1)]
    antes = _fim_do_dia(de - timedelta(days=1))
    # Escopo do burndown: tudo o que existia e não estava concluído antes do período, mais o que foi criado depois
    no_escopo = [h for h in historicos if h.situacao_em(antes) != "concluida"]
    inicial = sum(1 for h in no_escopo if h.situacao_em(antes) is not None)

    real: list[int | None] = []
    escopo: list[int] = []
    fluxo = {s: [] for s in STATUS_TAREFA}
    for dia in dias:
        fim = _fim_do_dia(dia)
        situacoes = [h.situacao_em(fim) for h in historicos]
        for s in STATUS_TAREFA:
            fluxo[s].append(sum(1 for x in situacoes if x == s))
        escopo.append(sum(1 for h in no_escopo if h.situacao_em(fim) is not None))
        real.append(None if dia > hoje else sum(1 for h in no_escopo if h.situacao_em(fim) not in (None, "concluida")))
    n = len(dias)
    ideal = [round(inicial * (n - 1 - i) / (n - 1), 2) if n > 1 else 0.0 for i in range(n)]

    # Vazão e ciclo por semana
    inicio_periodo, fim_periodo = _fim_do_dia(de - timedelta(days=1)), _fim_do_dia(ate)
    semanas = sorted({_segunda(d) for d in dias})
    criadas = {s: 0 for s in semanas}
    concluidas = {s: 0 for s in semanas}
    ciclos: dict[date, list[float]] = {s: [] for s in semanas}
    leads: dict[date, list[float]] = {s: [] for s in semanas}
    por_pessoa: dict[int, list[float]] = {}
    for h in historicos:
        criada = h.instantes[0]
        if inicio_periodo < criada <= fim_periodo:
            criadas[_segunda(criada.astimezone(FUSO).date())] += 1
        conclusoes = [c for c in h.conclusoes() if inicio_periodo < c <= fim_periodo]
        for c in conclusoes:
            semana = _segunda(c.astimezone(FUSO).date())
            concluidas[semana] += 1
            leads[semana].append(_dias(criada, c))
            inicio_trabalho = h.primeiro_inicio()
            if inicio_trabalho is not None and inicio_trabalho <= c:
                ciclos[semana].append(_dias(inicio_trabalho, c))
            for r in h.tarefa.responsaveis:
                por_pessoa.setdefault(r.usuario_id, []).append(_dias(criada, c))
    sequencia = [concluidas[s] for s in semanas]
    vazao = [{"semana_inicio": s, "criadas": criadas[s], "concluidas": concluidas[s],
              "media_movel": round(sum(sequencia[max(0, i - 3): i + 1]) / len(sequencia[max(0, i - 3): i + 1]), 2)} for i, s in enumerate(semanas)]
    ciclo = [{"semana_inicio": s, "concluidas": concluidas[s], "ciclo_mediana": _mediana(ciclos[s]), "ciclo_p85": _percentil(ciclos[s], 0.85),
              "lead_mediana": _mediana(leads[s]), "lead_p85": _percentil(leads[s], 0.85)} for s in semanas]

    from app.models.usuario import Usuario

    nomes = {u.id: u.nome_completo or u.login for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(list(por_pessoa))))} if por_pessoa else {}
    pessoas = sorted(
        ({"usuario_id": uid, "nome": nomes.get(uid, str(uid)), "concluidas": len(v), "lead_medio_dias": round(sum(v) / len(v), 1)} for uid, v in por_pessoa.items()),
        key=lambda p: (-p["concluidas"], p["nome"].lower()),
    )
    sla, sla_por_pessoa = _sla_do_periodo(sessao, historicos, inicio_periodo, fim_periodo)
    for p in pessoas:
        p["sla_percentual"] = sla_por_pessoa.get(p["usuario_id"])
    todos_ciclos = [x for lista in ciclos.values() for x in lista]
    todos_leads = [x for lista in leads.values() for x in lista]
    semanas_com_dados = max(1, len(semanas))
    return {
        "equipe_id": equipe_id, "equipe_nome": titulo, "de": de, "ate": ate, "tarefas_no_periodo": len(historicos),
        "resumo": {
            "abertas_agora": sum(1 for h in historicos if h.tarefa.status != "concluida"),
            "concluidas_no_periodo": sum(concluidas.values()), "criadas_no_periodo": sum(criadas.values()),
            "vazao_media_semanal": round(sum(concluidas.values()) / semanas_com_dados, 2),
            "ciclo_mediano_dias": _mediana(todos_ciclos), "lead_mediano_dias": _mediana(todos_leads),
        },
        "burndown": {"dias": dias, "real": real, "ideal": ideal, "escopo": escopo, "inicial": inicial},
        "vazao": vazao, "ciclo": ciclo,
        "fluxo": {"dias": dias, **{s: fluxo[s] for s in STATUS_TAREFA}},
        "pessoas": pessoas, "sla": sla,
    }
