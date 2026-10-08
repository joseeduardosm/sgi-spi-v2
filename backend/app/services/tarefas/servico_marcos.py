# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras dos marcos (milestones) da equipe e das atualizações de status da equipe.
"""Marcos e atualizações de status.

- **Marco:** nome, descrição e data-alvo da equipe; as tarefas ligadas a ele medem o progresso. Fica **atingido** quando todas as suas tarefas
  concluem (`servico_tarefas.reavaliar_marco`) ou por decisão da liderança (`atingir`, que o deixa fixo). Situação derivada: `atingido`,
  `atrasado` (data-alvo passou), `em_risco` (há tarefa atrasada ou com prazo depois da data-alvo) ou `no_prazo`.
- **Status da equipe:** a liderança publica uma atualização (no prazo, em risco, atrasado, em espera ou concluído) com texto; os membros são
  avisados (e-mail só em risco/atrasado). Toda segunda-feira a rotina das 07:00 lembra a liderança das equipes com tarefas abertas e sem
  atualização há 7 dias ou mais.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc, hoje_sao_paulo
from app.models.tarefas import SITUACOES_STATUS_EQUIPE, AtualizacaoStatusEquipe, EquipeTarefas, MarcoTarefa, Tarefa
from app.models.usuario import Usuario
from app.services import servico_mensagens
from app.services.servico_auditoria import auditar
from app.services.tarefas import servico_tarefas as servico
from app.services.tarefas.servico_tarefas import ErroTarefa

ROTULOS_SITUACAO = {"no_prazo": "No prazo", "em_risco": "Em risco", "atrasado": "Atrasado", "em_espera": "Em espera", "concluido": "Concluído"}


@dataclass
class DadosMarco:
    nome: str
    data_alvo: date
    descricao: str = ""


def _equipe_visivel(sessao: Session, usuario: Usuario, equipe_id: uuid.UUID, lider: bool = False) -> EquipeTarefas:
    equipe = sessao.get(EquipeTarefas, equipe_id)
    eh_lider = equipe is not None and (usuario.superusuario or usuario.id in servico.lideranca(sessao, equipe))
    if equipe is None or not (eh_lider or usuario.id in servico.membros(equipe)):
        raise ErroTarefa("Equipe não encontrada.", 404, "nao_encontrado")
    if lider and not eh_lider:
        raise ErroTarefa("Só a liderança da equipe faz isso.", 403, "sem_permissao")
    return equipe


def progresso(sessao: Session, marco: MarcoTarefa, hoje: date | None = None) -> dict:
    """Total, concluídas e atrasadas das tarefas do marco e a situação derivada."""
    hoje = hoje or hoje_sao_paulo()
    tarefas = list(sessao.scalars(select(Tarefa).where(Tarefa.marco_id == marco.id)))
    abertas = [t for t in tarefas if t.status != "concluida"]
    agora = agora_utc()
    atrasadas = [t for t in abertas if t.status in servico.OPERACIONAIS and servico._comparavel(t.prazo) < agora]
    depois_do_alvo = [t for t in abertas if servico._comparavel(t.prazo).astimezone(servico.FUSO_LOCAL).date() > marco.data_alvo]
    if marco.atingido_em is not None:
        situacao = "atingido"
    elif marco.data_alvo < hoje:
        situacao = "atrasado"
    elif atrasadas or depois_do_alvo:
        situacao = "em_risco"
    else:
        situacao = "no_prazo"
    return {"total": len(tarefas), "concluidas": len(tarefas) - len(abertas), "atrasadas": len(atrasadas), "situacao": situacao}


def listar(sessao: Session, usuario: Usuario, equipe_id: uuid.UUID) -> list[tuple[MarcoTarefa, dict]]:
    _equipe_visivel(sessao, usuario, equipe_id)
    marcos = list(sessao.scalars(select(MarcoTarefa).where(MarcoTarefa.equipe_id == equipe_id).order_by(MarcoTarefa.data_alvo, MarcoTarefa.nome)))
    return [(m, progresso(sessao, m)) for m in marcos]


def obter(sessao: Session, usuario: Usuario, marco_id: uuid.UUID, lider: bool = False) -> MarcoTarefa:
    marco = sessao.get(MarcoTarefa, marco_id)
    if marco is None:
        raise ErroTarefa("Marco não encontrado.", 404, "nao_encontrado")
    _equipe_visivel(sessao, usuario, marco.equipe_id, lider)
    return marco


def salvar(sessao: Session, autor: Usuario, equipe_id: uuid.UUID, dados: DadosMarco, marco: MarcoTarefa | None = None) -> MarcoTarefa:
    _equipe_visivel(sessao, autor, equipe_id, lider=True)
    nome = dados.nome.strip()
    if not nome:
        raise ErroTarefa("Informe o nome do marco.")
    repetido = sessao.scalar(select(MarcoTarefa).where(MarcoTarefa.equipe_id == equipe_id, func.lower(MarcoTarefa.nome) == nome.lower()))
    if repetido is not None and (marco is None or repetido.id != marco.id):
        raise ErroTarefa("Já existe um marco com esse nome na equipe.", 409, "conflito")
    marco = marco or MarcoTarefa(equipe_id=equipe_id, criado_por_id=autor.id)
    marco.nome, marco.descricao, marco.data_alvo = nome, dados.descricao.strip(), dados.data_alvo
    sessao.add(marco)
    auditar(sessao, autor.login, "tarefas.marco.salvar", nome, autor_id=autor.id, alvo_tipo="tarefa-equipe", alvo_id=equipe_id)
    sessao.commit()
    return marco


def excluir(sessao: Session, autor: Usuario, marco: MarcoTarefa) -> None:
    """As tarefas continuam, sem marco."""
    sessao.delete(marco)
    sessao.commit()


def atingir(sessao: Session, autor: Usuario, marco: MarcoTarefa, atingido: bool) -> MarcoTarefa:
    """Decisão manual da liderança: marca como atingido (ou reabre) e deixa o estado fixo, sem a conclusão automática das tarefas."""
    marco.atingido_manual = True
    marco.atingido_em = agora_utc() if atingido else None
    sessao.commit()
    return marco


def definir_marco_da_tarefa(sessao: Session, autor: Usuario, tarefa: Tarefa, marco_id: uuid.UUID | None) -> Tarefa:
    servico._exigir(servico.pode_editar(sessao, autor, tarefa), "Você não pode alterar esta tarefa.")
    servico._exigir_nao_concluida(tarefa, "mudar o marco")
    anterior = tarefa.marco_id
    if marco_id is not None:
        marco = sessao.get(MarcoTarefa, marco_id)
        if marco is None or marco.equipe_id != tarefa.equipe_id:
            raise ErroTarefa("O marco precisa ser da mesma equipe da tarefa.")
    if marco_id != anterior:
        nomes = {m.id: m.nome for m in sessao.scalars(select(MarcoTarefa).where(MarcoTarefa.id.in_([x for x in (marco_id, anterior) if x]))) } if (marco_id or anterior) else {}
        servico._evento(sessao, tarefa, "editada", autor, f"Marco: {nomes.get(anterior, '—')} → {nomes.get(marco_id, '—')}")
        tarefa.marco_id = marco_id
        tarefa.versao += 1
        sessao.flush()
        servico.reavaliar_marco(sessao, anterior)
        servico.reavaliar_marco(sessao, marco_id)
    sessao.commit()
    return tarefa


# --- Status da equipe ---------------------------------------------------------------------------------------------------------------

def historico(sessao: Session, usuario: Usuario, equipe_id: uuid.UUID, limite: int = 30) -> list[AtualizacaoStatusEquipe]:
    _equipe_visivel(sessao, usuario, equipe_id)
    return list(sessao.scalars(select(AtualizacaoStatusEquipe).where(AtualizacaoStatusEquipe.equipe_id == equipe_id).order_by(AtualizacaoStatusEquipe.criado_em.desc()).limit(limite)))


def publicar(sessao: Session, autor: Usuario, equipe_id: uuid.UUID, situacao: str, texto: str) -> AtualizacaoStatusEquipe:
    equipe = _equipe_visivel(sessao, autor, equipe_id, lider=True)
    if situacao not in SITUACOES_STATUS_EQUIPE:
        raise ErroTarefa("Situação inválida.")
    atualizacao = AtualizacaoStatusEquipe(equipe_id=equipe_id, situacao=situacao, texto=texto.strip(), autor_id=autor.id, autor_nome=servico._nome(autor))
    sessao.add(atualizacao)
    sessao.flush()
    destinatarios = (servico.lideranca(sessao, equipe) | servico.membros(equipe))
    servico_mensagens.notificar(
        sessao, list(destinatarios), f"Status da equipe {equipe.nome}: {ROTULOS_SITUACAO[situacao]}",
        f"{servico._nome(autor)} atualizou a situação da equipe para \"{ROTULOS_SITUACAO[situacao]}\"." + (f"\n\n{atualizacao.texto}" if atualizacao.texto else ""),
        chave=f"tarefa-status-equipe:{atualizacao.id}", categoria="comunicado", prioridade="alta" if situacao in ("em_risco", "atrasado") else "normal",
        link=f"/tarefas/equipes/{equipe.id}", email=situacao in ("em_risco", "atrasado"), autor=autor,
    )
    auditar(sessao, autor.login, "tarefas.status_equipe", equipe.nome, ROTULOS_SITUACAO[situacao], autor_id=autor.id, alvo_tipo="tarefa-equipe", alvo_id=equipe.id)
    sessao.commit()
    return atualizacao


def lembrar(sessao: Session, dia: date | None = None) -> int:
    """Toda segunda-feira, lembra a liderança das equipes com tarefas abertas e sem atualização de status há 7 dias ou mais."""
    dia = dia or hoje_sao_paulo()
    if dia.weekday() != 0:
        return 0
    lembradas = 0
    limite = datetime.combine(dia - timedelta(days=7), datetime.min.time(), tzinfo=servico.FUSO_LOCAL)
    for equipe in sessao.scalars(select(EquipeTarefas).where(EquipeTarefas.ativa.is_(True))):
        abertas = sessao.scalar(select(func.count(Tarefa.id)).where(Tarefa.equipe_id == equipe.id, Tarefa.status != "concluida")) or 0
        ultima = sessao.scalar(select(func.max(AtualizacaoStatusEquipe.criado_em)).where(AtualizacaoStatusEquipe.equipe_id == equipe.id))
        if not abertas or (ultima is not None and servico._comparavel(ultima) > limite):
            continue
        if servico_mensagens.notificar(
            sessao, list(servico.lideranca(sessao, equipe)), f"Atualize o status da equipe {equipe.nome}",
            f"A equipe {equipe.nome} tem {abertas} tarefa(s) aberta(s) e nenhuma atualização de status na última semana. Publique a situação (no prazo, em risco…).",
            chave=f"tarefa-status-lembrete:{equipe.id}:{dia}", categoria="pendencia", link=f"/tarefas/equipes/{equipe.id}", email=True,
        ):
            lembradas += 1
    sessao.commit()
    return lembradas
