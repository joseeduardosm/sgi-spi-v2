# Criado por José Eduardo Santana Martins
# Este arquivo serve para os módulos do sistema (ex.: Contratos) criarem e moverem tarefas por código, sem as regras de quem usa a tela.
"""Tarefas criadas e movidas por outro módulo ("origem").

Diferenças para `servico_tarefas.criar` e `servico_tarefas.mover`:
- não conferem permissão (quem decide é o módulo de origem) nem dão `commit` (fazem parte da transação do chamador);
- não mandam aviso por tarefa (o chamador manda um resumo, se quiser);
- a data de cada evento é informada (`quando`), para tarefas espelhadas de um estado antigo ficarem com as datas reais,
  e o histórico da tarefa (`status` com de/para) continua servindo ao Desempenho (burndown, ciclo e lead time).
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.tarefas import EquipeTarefas, MarcadorTarefa, ResponsavelTarefa, Tarefa
from app.models.usuario import Usuario
from app.services.tarefas import servico_tarefas as servico


def criar_de_origem(sessao: Session, autor: Usuario, equipe: EquipeTarefas, titulo: str, descricao: str, prazo: datetime,
                    responsaveis_ids: list[int], marcadores: list[MarcadorTarefa], origem_tipo: str, origem_id: uuid.UUID, origem_chave: str,
                    controlada: bool, nascimento: datetime | None = None, prioridade: str = "normal", evento_titulo: str = "Tarefa criada") -> Tarefa:
    """Cria a tarefa (sempre "a fazer") ligada à origem. `nascimento` define o momento da criação (padrão: agora)."""
    nascimento = nascimento or agora_utc()
    numero = (sessao.scalar(select(func.max(Tarefa.numero))) or 0) + 1
    principal = responsaveis_ids[0]
    tarefa = Tarefa(
        numero=numero, titulo=titulo[:200], descricao=descricao, equipe_id=equipe.id, criado_por_id=autor.id, responsavel_id=principal,
        prazo=prazo, prazo_original=prazo, prioridade=prioridade, ordem=-numero, criado_em=nascimento,
        origem_tipo=origem_tipo, origem_id=origem_id, origem_chave=origem_chave, controlada_externamente=controlada,
    )
    tarefa.equipe = equipe
    tarefa.estagio_id = servico.estagio_da_categoria(sessao, equipe.id, "a_fazer")
    tarefa.responsaveis = [ResponsavelTarefa(usuario_id=i) for i in sorted(set(responsaveis_ids))]
    tarefa.marcadores = list(marcadores)
    sessao.add(tarefa)
    sessao.flush()
    evento = servico._evento(sessao, tarefa, "criada", autor, evento_titulo, prazo=prazo.isoformat(), responsavel=servico._nome(sessao.get(Usuario, principal)))
    evento.criado_em = nascimento
    return tarefa


def evento_de_origem(sessao: Session, tarefa: Tarefa, autor: Usuario | None, titulo: str, texto: str = "", quando: datetime | None = None, **dados) -> None:
    """Registra na linha do tempo o que aconteceu no módulo de origem (tipo `contrato`): quem fez e o que fez na etapa."""
    evento = servico._evento(sessao, tarefa, "contrato", autor, titulo, texto, **dados)
    evento.criado_em = quando or agora_utc()


def aplicar_status(sessao: Session, tarefa: Tarefa, para: str, autor: Usuario | None, titulo: str, texto: str = "", quando: datetime | None = None) -> None:
    """Leva a tarefa à situação `para` sem checar permissão nem avisar, mantendo os carimbos e o evento de/para (como `servico_tarefas.mover`)."""
    de = tarefa.status
    if de == para:
        return
    quando = quando or agora_utc()
    if tarefa.em_andamento_desde is not None:
        tarefa.segundos_em_andamento += max(0, int((quando - servico._comparavel(tarefa.em_andamento_desde)).total_seconds()))
        tarefa.em_andamento_desde = None
    if para == "em_andamento":
        tarefa.em_andamento_desde = quando
        tarefa.iniciada_em = tarefa.iniciada_em or quando
    tarefa.concluida_em = quando if para == "concluida" else None
    tarefa.status, tarefa.versao = para, tarefa.versao + 1
    tarefa.estagio_id = servico.estagio_da_categoria(sessao, tarefa.equipe_id, para)
    tarefa.atualizado_em = quando
    servico.reavaliar_marco(sessao, tarefa.marco_id)
    tipo = "reaberta" if de == "concluida" else "status"
    evento = servico._evento(sessao, tarefa, tipo, autor, titulo, texto, de=de, para=para)
    evento.criado_em = quando


def alterar_prazo(sessao: Session, tarefa: Tarefa, novo: datetime, autor: Usuario | None, texto: str, redefinir_original: bool = False) -> None:
    """Muda o prazo por decisão do módulo de origem (ex.: vencimento do pagamento conhecido só depois), com evento na linha do tempo."""
    anterior = tarefa.prazo
    if servico._comparavel(anterior) == servico._comparavel(novo):
        return
    tarefa.prazo, tarefa.versao = novo, tarefa.versao + 1
    if redefinir_original:
        tarefa.prazo_original = novo
    servico._evento(sessao, tarefa, "prazo", autor, "Prazo ajustado pelo módulo Contratos", texto, de=anterior.isoformat(), para=novo.isoformat())


def trocar_responsaveis(tarefa: Tarefa, ids: list[int]) -> bool:
    """Põe os responsáveis em `ids` (o primeiro é o principal). Devolve se algo mudou."""
    if not ids or {p.usuario_id for p in tarefa.responsaveis} == set(ids) and tarefa.responsavel_id == ids[0]:
        return False
    tarefa.responsaveis = [p for p in tarefa.responsaveis if p.usuario_id in ids] + [
        ResponsavelTarefa(usuario_id=i) for i in sorted(set(ids) - {p.usuario_id for p in tarefa.responsaveis})]
    tarefa.responsavel_id = ids[0]
    return True


__all__ = ["criar_de_origem", "evento_de_origem", "aplicar_status", "alterar_prazo", "trocar_responsaveis"]
