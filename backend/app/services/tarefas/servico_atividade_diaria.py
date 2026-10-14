# Criado por José Eduardo Santana Martins
# Este arquivo serve para montar a visão "O que aconteceu": por dia, em cada tarefa da equipe, o que foi feito (para a liderança).
"""Atividade diária da equipe: dia > tarefa > o que houve.

Junta os eventos da linha do tempo (`tarefas_eventos`) de todas as tarefas da equipe e das subequipes, **inclusive as subtarefas**, e os organiza por dia
(fuso de São Paulo). Só a liderança da equipe (ou o SuperRoot) vê. Redução de ruído: os itens de checklist do mesmo dia numa tarefa viram uma linha e os
avisos automáticos (escalonamento e eventos sem autor) ficam de fora, a não ser que sejam pedidos.
"""

import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import FUSO_SAO_PAULO, em_sao_paulo
from app.models.tarefas import EquipeTarefas, EventoTarefa, Tarefa
from app.models.usuario import Usuario
from app.services.tarefas import servico_tarefas as servico
from app.services.tarefas.servico_tarefas import ErroTarefa

MAXIMO_DIAS = 31
# Grupos de tipo aceitos no filtro `tipos`
GRUPOS = {
    "entregas": ("entregue", "validada", "devolvida", "reaberta"),
    "comentarios": ("comentario",),
    "prazos": ("prazo",),
    "situacao": ("status", "criada"),
    "atribuicoes": ("transferida", "participantes"),
    "outros": ("editada", "marcadores", "checklist", "atividade", "contrato", "escalonada"),
}
AUTOMATICOS = ("escalonada",)
TRECHO = 240


def _limites(de: date, ate: date) -> tuple[datetime, datetime]:
    """Início do primeiro dia e início do dia seguinte ao último, em UTC (os dias são os de São Paulo)."""
    inicio = datetime.combine(de, time.min, FUSO_SAO_PAULO).astimezone(timezone.utc)
    fim = datetime.combine(ate + timedelta(days=1), time.min, FUSO_SAO_PAULO).astimezone(timezone.utc)
    return inicio, fim


def _trecho(texto: str) -> str:
    texto = (texto or "").strip()
    return texto if len(texto) <= TRECHO else texto[:TRECHO] + "…"


def _tipos_pedidos(grupos: list[str] | None) -> set[str] | None:
    if not grupos:
        return None
    desconhecido = [g for g in grupos if g not in GRUPOS]
    if desconhecido:
        raise ErroTarefa(f"Tipo desconhecido: {', '.join(desconhecido)}.")
    return {t for g in grupos for t in GRUPOS[g]}


def atividade_da_equipe(
    sessao: Session, usuario: Usuario, equipe_id: uuid.UUID, de: date, ate: date, *, pessoa_id: int | None = None, grupos: list[str] | None = None,
    incluir_automaticos: bool = False, busca: str = "",
) -> dict:
    equipe = sessao.get(EquipeTarefas, equipe_id)
    if equipe is None or equipe not in servico.equipes_visiveis(sessao, usuario):
        raise ErroTarefa("Equipe não encontrada.", 404, "nao_encontrado")
    if not (usuario.superusuario or usuario.id in servico.lideranca(sessao, equipe)):
        raise ErroTarefa("Só a liderança da equipe vê a atividade diária.", 403, "acl_negado")
    if de > ate:
        raise ErroTarefa("O início do período é depois do fim.")
    if (ate - de).days + 1 > MAXIMO_DIAS:
        raise ErroTarefa(f"O período vai até {MAXIMO_DIAS} dias.")
    tipos = _tipos_pedidos(grupos)
    ids_equipes = [e.id for e in servico._com_subequipes(sessao, equipe)]
    inicio, fim = _limites(de, ate)
    consulta = (
        select(EventoTarefa, Tarefa).join(Tarefa, Tarefa.id == EventoTarefa.tarefa_id)
        .where(Tarefa.equipe_id.in_(ids_equipes), EventoTarefa.criado_em >= inicio, EventoTarefa.criado_em < fim,
               EventoTarefa.removido_em.is_(None), EventoTarefa.tipo != "removido")
        .order_by(EventoTarefa.criado_em)
    )
    if pessoa_id is not None:
        consulta = consulta.where(EventoTarefa.autor_id == pessoa_id)
    if tipos is not None:
        consulta = consulta.where(EventoTarefa.tipo.in_(tipos))
    termo = (busca or "").strip().lower().lstrip("#")

    # dia -> tarefa -> eventos (ordem cronológica)
    por_dia: dict[date, dict[uuid.UUID, list[EventoTarefa]]] = defaultdict(lambda: defaultdict(list))
    tarefas: dict[uuid.UUID, Tarefa] = {}
    automaticos_ocultos: dict[date, int] = defaultdict(int)
    for evento, tarefa in sessao.execute(consulta):
        if termo and termo not in tarefa.titulo.lower() and termo != str(tarefa.numero):
            continue
        dia = em_sao_paulo(evento.criado_em).date()
        if not incluir_automaticos and (evento.tipo in AUTOMATICOS or evento.autor_id is None and evento.tipo not in ("criada", "contrato", "status")):
            automaticos_ocultos[dia] += 1
            continue
        por_dia[dia][tarefa.id].append(evento)
        tarefas[tarefa.id] = tarefa

    numeros_maes = {t.id: t.numero for t in sessao.scalars(select(Tarefa).where(Tarefa.id.in_({t.tarefa_pai_id for t in tarefas.values() if t.tarefa_pai_id})))} if tarefas else {}
    dias = []
    for dia in sorted({*por_dia, *automaticos_ocultos}, reverse=True):
        blocos = []
        resumo = {"tarefas": 0, "entregues": 0, "concluidas": 0, "comentarios": 0, "automaticos_ocultos": automaticos_ocultos.get(dia, 0)}
        for tarefa_id, eventos in por_dia.get(dia, {}).items():
            tarefa = tarefas[tarefa_id]
            itens, checklist = [], []
            for e in eventos:
                if e.tipo == "checklist":
                    checklist.append(e)
                    continue
                itens.append(_item(e))
                resumo["entregues"] += e.tipo == "entregue"
                resumo["comentarios"] += e.tipo == "comentario"
                resumo["concluidas"] += e.tipo == "validada" or (e.tipo == "status" and (e.dados or {}).get("para") == "concluida")
            if checklist:
                ultimo = checklist[-1]
                item = _item(ultimo)
                if len(checklist) > 1:
                    item.update(titulo=f"{len(checklist)} alterações no checklist", texto="", agrupados=len(checklist))
                itens.append(item)
            itens.sort(key=lambda i: i["hora"])
            blocos.append({
                "numero": tarefa.numero, "titulo": tarefa.titulo, "status": tarefa.status, "equipe_nome": tarefa.equipe.nome if tarefa.equipe else None,
                "tarefa_pai_numero": numeros_maes.get(tarefa.tarefa_pai_id), "ultima": itens[-1]["hora"], "itens": itens,
            })
        blocos.sort(key=lambda b: b["ultima"], reverse=True)
        resumo["tarefas"] = len(blocos)
        dias.append({"data": dia, "resumo": resumo, "tarefas": blocos})
    return {"de": de, "ate": ate, "equipe_id": equipe.id, "dias": dias}


def _item(e: EventoTarefa) -> dict:
    dados = e.dados or {}
    # Só o que a tela precisa para contar a história (de/para, destinatário, motivo); o resto do JSON fica de fora
    uteis = {k: dados[k] for k in ("de", "para", "prazo", "prazo_para", "responsavel", "destino", "motivo", "resposta_autor") if k in dados}
    return {
        "id": e.id, "hora": e.criado_em if e.criado_em.tzinfo else e.criado_em.replace(tzinfo=timezone.utc), "tipo": e.tipo, "titulo": e.titulo, "texto": _trecho(e.texto),
        "autor": e.autor_nome, "autor_id": e.autor_id, "dados": uteis, "automatico": e.tipo in AUTOMATICOS or e.autor_id is None, "agrupados": 1,
    }
