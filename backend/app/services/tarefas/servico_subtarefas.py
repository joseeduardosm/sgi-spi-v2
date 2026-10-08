# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras das subtarefas e das dependências entre tarefas.
"""Subtarefas e dependências.

- **Subtarefa:** tarefa de verdade (pipeline, responsáveis, prazo), ligada a uma mãe; só um nível (subtarefa não tem subtarefa).
  Herda equipe e marcadores da mãe; o prazo não passa do da mãe; sem responsáveis informados, vão os da mãe. A mãe só entra em
  validação ou conclui com todas as subtarefas concluídas (`servico_tarefas.mover`). Excluir a mãe leva as subtarefas (cascata no banco).
- **Dependência:** "bloqueada por": a tarefa não inicia enquanto a bloqueadora não for concluída (`servico_tarefas.mover`). As duas
  precisam ser da mesma equipe, não pode haver ciclo nem a tarefa depender de si mesma ou da própria mãe/subtarefa.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.tarefas import DependenciaTarefa, Tarefa
from app.models.usuario import Usuario
from app.services.servico_auditoria import auditar
from app.services.tarefas import servico_tarefas as servico
from app.services.tarefas.servico_tarefas import DadosTarefa, ErroTarefa


@dataclass
class DadosSubtarefa:
    titulo: str
    descricao: str = ""
    prazo: datetime | None = None
    prioridade: str | None = None
    responsaveis_ids: tuple[int, ...] = ()


def criar_subtarefa(sessao: Session, autor: Usuario, mae: Tarefa, dados: DadosSubtarefa) -> Tarefa:
    """Cria a subtarefa da `mae` (quem edita a mãe pode)."""
    servico._exigir(servico.pode_editar(sessao, autor, mae), "Você não pode criar subtarefas desta tarefa.")
    servico._exigir_nao_concluida(mae, "criar subtarefas")
    servico.exigir_nao_controlada(mae, "criar subtarefas")
    if mae.tarefa_pai_id is not None:
        raise ErroTarefa("Uma subtarefa não pode ter subtarefas.")
    prazo = dados.prazo or mae.prazo
    if servico._comparavel(prazo) > servico._comparavel(mae.prazo):
        raise ErroTarefa("O prazo da subtarefa não pode passar do prazo da tarefa mãe.")
    responsaveis = dados.responsaveis_ids or tuple([mae.responsavel_id, *sorted(servico.envolvidos(mae) - {mae.responsavel_id})] if mae.responsavel_id else sorted(servico.envolvidos(mae)))
    sub = servico.criar(sessao, autor, DadosTarefa(
        titulo=dados.titulo, descricao=dados.descricao, prazo=prazo, prioridade=dados.prioridade or mae.prioridade, equipe_id=mae.equipe_id,
        responsaveis_ids=tuple(responsaveis), marcadores_ids=tuple(m.id for m in mae.marcadores), tarefa_pai_id=mae.id,
    ))
    servico._evento(sessao, mae, "editada", autor, f"Subtarefa criada: #{sub.numero} {sub.titulo}")
    sessao.commit()
    return sub


def _alcanca(sessao: Session, origem: uuid.UUID, procurada: uuid.UUID) -> bool:
    """A tarefa `origem` depende (direta ou indiretamente) da `procurada`?"""
    visitadas: set[uuid.UUID] = set()
    fila = [origem]
    while fila:
        atual = fila.pop()
        if atual == procurada:
            return True
        if atual in visitadas:
            continue
        visitadas.add(atual)
        fila += list(sessao.scalars(select(DependenciaTarefa.bloqueada_por_id).where(DependenciaTarefa.tarefa_id == atual)))
    return False


def definir_dependencias(sessao: Session, autor: Usuario, tarefa: Tarefa, numeros: list[int]) -> Tarefa:
    """Substitui a lista de tarefas que bloqueiam esta (por número)."""
    servico._exigir(servico.pode_editar(sessao, autor, tarefa), "Você não pode alterar as dependências desta tarefa.")
    servico._exigir_nao_concluida(tarefa, "alterar dependências")
    servico.exigir_nao_controlada(tarefa, "alterar dependências")
    numeros = list(dict.fromkeys(numeros))
    bloqueadoras = list(sessao.scalars(select(Tarefa).where(Tarefa.numero.in_(numeros)))) if numeros else []
    if len(bloqueadoras) != len(numeros):
        raise ErroTarefa("Alguma tarefa informada não existe.")
    for b in bloqueadoras:
        if b.id == tarefa.id:
            raise ErroTarefa("Uma tarefa não pode ser bloqueada por ela mesma.")
        if not servico.pode_ver(sessao, autor, b):
            raise ErroTarefa(f"Você não tem acesso à tarefa #{b.numero}.")
        if b.equipe_id != tarefa.equipe_id:
            raise ErroTarefa(f"A tarefa #{b.numero} é de outra equipe: só é possível depender de tarefas da mesma equipe.")
        if tarefa.id in (b.tarefa_pai_id,) or b.id == tarefa.tarefa_pai_id:
            raise ErroTarefa("Uma tarefa não pode depender da própria tarefa mãe ou subtarefa.")
        if _alcanca(sessao, b.id, tarefa.id):
            raise ErroTarefa(f"A dependência de #{b.numero} cria um ciclo (ela já depende desta tarefa).")
    antes = {n for n in sessao.scalars(select(Tarefa.numero).join(DependenciaTarefa, DependenciaTarefa.bloqueada_por_id == Tarefa.id).where(DependenciaTarefa.tarefa_id == tarefa.id))}
    sessao.execute(delete(DependenciaTarefa).where(DependenciaTarefa.tarefa_id == tarefa.id))
    for b in bloqueadoras:
        sessao.add(DependenciaTarefa(tarefa_id=tarefa.id, bloqueada_por_id=b.id))
    if antes != set(numeros):
        texto = ", ".join(f"#{n}" for n in sorted(numeros)) or "nenhuma"
        servico._evento(sessao, tarefa, "editada", autor, "Dependências alteradas", f"Bloqueada por: {texto}")
        tarefa.versao += 1
        auditar(sessao, autor.login, "tarefas.dependencias", servico._rotulo(tarefa), texto, autor_id=autor.id, alvo_tipo="tarefa", alvo_id=tarefa.id)
    sessao.commit()
    return tarefa
