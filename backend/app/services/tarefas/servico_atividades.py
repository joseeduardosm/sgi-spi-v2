# Criado por José Eduardo Santana Martins
# Este arquivo serve para as atividades agendadas das tarefas (ligar, revisar, enviar documento…), os seguidores e os lembretes diários.
"""Atividades agendadas e seguidores.

- Uma **atividade** é um compromisso curto dentro da tarefa, com tipo, resumo, nota, **data** e uma pessoa responsável (padrão: quem agenda).
  Quem agenda para outra pessoa a avisa na hora (com e-mail). Concluir aceita um feedback e registra na linha do tempo da tarefa.
- A rotina das 07:00 (`lembrar`) avisa o responsável das atividades **de hoje** e das **atrasadas** (e quem agendou, quando é outra pessoa),
  no máximo uma vez por dia; concluir ou excluir a atividade encerra o aviso.
- **Seguidores** acompanham a tarefa sem serem responsáveis e recebem os avisos informativos (comentários, prazos, validação).
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc, hoje_sao_paulo
from app.models.tarefas import TIPOS_ATIVIDADE, AtividadeTarefa, SeguidorTarefa, Tarefa
from app.models.usuario import Usuario
from app.services import servico_mensagens
from app.services.servico_auditoria import auditar
from app.services.tarefas import servico_tarefas as servico
from app.services.tarefas.servico_tarefas import ErroTarefa

ROTULOS_TIPO = {"fazer": "A fazer", "ligar": "Ligar", "email": "E-mail", "reuniao": "Reunião", "revisar": "Revisar", "enviar_documento": "Enviar documento"}


@dataclass
class DadosAtividade:
    resumo: str
    tipo: str = "fazer"
    nota: str = ""
    prazo: date | None = None
    responsavel_id: int | None = None


def _pode_agendar(sessao: Session, usuario: Usuario, tarefa: Tarefa) -> bool:
    return usuario.id in servico.envolvidos(tarefa) or servico.pode_editar(sessao, usuario, tarefa)


def _validar(dados: DadosAtividade) -> None:
    if dados.tipo not in TIPOS_ATIVIDADE:
        raise ErroTarefa("Tipo de atividade inválido.")
    if not dados.resumo.strip():
        raise ErroTarefa("Informe o resumo da atividade.")


def listar(sessao: Session, usuario: Usuario, tarefa: Tarefa) -> list[AtividadeTarefa]:
    """Atividades da tarefa: abertas primeiro (por data) e depois as concluídas (mais recentes antes)."""
    lista = list(sessao.scalars(select(AtividadeTarefa).where(AtividadeTarefa.tarefa_id == tarefa.id)))
    abertas = sorted((a for a in lista if a.concluida_em is None), key=lambda a: (a.prazo, a.criada_em))
    feitas = sorted((a for a in lista if a.concluida_em is not None), key=lambda a: a.concluida_em, reverse=True)
    return abertas + feitas


def criar(sessao: Session, autor: Usuario, tarefa: Tarefa, dados: DadosAtividade) -> AtividadeTarefa:
    servico._exigir(_pode_agendar(sessao, autor, tarefa), "Você não pode agendar atividades nesta tarefa.")
    servico._exigir_nao_concluida(tarefa, "agendar atividades")
    _validar(dados)
    responsavel = dados.responsavel_id or autor.id
    servico._usuario_ativo(sessao, responsavel)
    if responsavel != autor.id and tarefa.equipe is not None:
        servico._conferir_pessoas(sessao, autor, tarefa.equipe, {responsavel})
    atividade = AtividadeTarefa(
        tarefa_id=tarefa.id, tipo=dados.tipo, resumo=dados.resumo.strip(), nota=dados.nota.strip(), prazo=dados.prazo or hoje_sao_paulo(),
        responsavel_id=responsavel, criada_por_id=autor.id,
    )
    sessao.add(atividade)
    sessao.flush()
    servico._evento(sessao, tarefa, "atividade", autor, f"Atividade agendada: {ROTULOS_TIPO[atividade.tipo]} · {atividade.resumo}",
                    f"Para {servico._nome(sessao.get(Usuario, responsavel))} até {atividade.prazo:%d/%m/%Y}." + (f"\n{atividade.nota}" if atividade.nota else ""))
    if responsavel != autor.id:
        servico._avisar(sessao, {responsavel}, f"Atividade agendada para você: {atividade.resumo}",
                        f"{servico._nome(autor)} agendou para você ({ROTULOS_TIPO[atividade.tipo]}), até {atividade.prazo:%d/%m/%Y}, na tarefa {servico._rotulo(tarefa)}.",
                        tarefa, f"tarefa-atividade:{atividade.id}", autor=autor)
    auditar(sessao, autor.login, "tarefas.atividade.criar", servico._rotulo(tarefa), atividade.resumo, autor_id=autor.id, alvo_tipo="tarefa", alvo_id=tarefa.id)
    sessao.commit()
    return atividade


def obter(sessao: Session, usuario: Usuario, atividade_id: uuid.UUID) -> tuple[AtividadeTarefa, Tarefa]:
    atividade = sessao.get(AtividadeTarefa, atividade_id)
    tarefa = sessao.get(Tarefa, atividade.tarefa_id) if atividade else None
    if atividade is None or tarefa is None or not servico.pode_ver(sessao, usuario, tarefa):
        raise ErroTarefa("Atividade não encontrada.", 404, "nao_encontrado")
    return atividade, tarefa


def _pode_mexer(sessao: Session, usuario: Usuario, atividade: AtividadeTarefa, tarefa: Tarefa) -> bool:
    return usuario.id in (atividade.responsavel_id, atividade.criada_por_id) or servico.pode_editar(sessao, usuario, tarefa)


def atualizar(sessao: Session, autor: Usuario, atividade: AtividadeTarefa, tarefa: Tarefa, dados: DadosAtividade) -> AtividadeTarefa:
    servico._exigir(_pode_mexer(sessao, autor, atividade, tarefa), "Você não pode alterar esta atividade.")
    if atividade.concluida_em is not None:
        raise ErroTarefa("A atividade já foi concluída.", 409, "conflito")
    _validar(dados)
    atividade.tipo, atividade.resumo, atividade.nota = dados.tipo, dados.resumo.strip(), dados.nota.strip()
    if dados.prazo:
        atividade.prazo = dados.prazo
    if dados.responsavel_id and dados.responsavel_id != atividade.responsavel_id:
        servico._usuario_ativo(sessao, dados.responsavel_id)
        atividade.responsavel_id = dados.responsavel_id
    servico_mensagens.encerrar(sessao, prefixo=f"tarefa-atividade-lembrete:{atividade.id}:")
    sessao.commit()
    return atividade


def concluir(sessao: Session, autor: Usuario, atividade: AtividadeTarefa, tarefa: Tarefa, feedback: str = "") -> AtividadeTarefa:
    servico._exigir(_pode_mexer(sessao, autor, atividade, tarefa), "Você não pode concluir esta atividade.")
    if atividade.concluida_em is not None:
        raise ErroTarefa("A atividade já foi concluída.", 409, "conflito")
    atividade.concluida_em, atividade.concluida_por_id, atividade.feedback = agora_utc(), autor.id, feedback.strip()
    servico._evento(sessao, tarefa, "atividade", autor, f"Atividade concluída: {ROTULOS_TIPO[atividade.tipo]} · {atividade.resumo}", atividade.feedback)
    servico_mensagens.encerrar(sessao, prefixo=f"tarefa-atividade-lembrete:{atividade.id}:")
    if atividade.criada_por_id and atividade.criada_por_id != autor.id:
        servico._avisar(sessao, {atividade.criada_por_id}, f"Atividade concluída: {atividade.resumo}",
                        f"{servico._nome(autor)} concluiu a atividade \"{atividade.resumo}\" da tarefa {servico._rotulo(tarefa)}."
                        + (f"\n\nFeedback: {atividade.feedback}" if atividade.feedback else ""), tarefa, f"tarefa-atividade-feita:{atividade.id}", autor=autor, categoria="comunicado")
    sessao.commit()
    return atividade


def excluir(sessao: Session, autor: Usuario, atividade: AtividadeTarefa, tarefa: Tarefa) -> None:
    servico._exigir(_pode_mexer(sessao, autor, atividade, tarefa), "Você não pode excluir esta atividade.")
    servico_mensagens.encerrar(sessao, prefixo=f"tarefa-atividade-lembrete:{atividade.id}:")
    sessao.delete(atividade)
    sessao.commit()


def minhas(sessao: Session, usuario: Usuario, concluidas: bool = False) -> list[tuple[AtividadeTarefa, Tarefa]]:
    """Atividades da pessoa (abertas por data ou as últimas concluídas) com a tarefa de cada uma."""
    consulta = select(AtividadeTarefa, Tarefa).join(Tarefa, Tarefa.id == AtividadeTarefa.tarefa_id).where(AtividadeTarefa.responsavel_id == usuario.id)
    if concluidas:
        linhas = sessao.execute(consulta.where(AtividadeTarefa.concluida_em.is_not(None)).order_by(AtividadeTarefa.concluida_em.desc()).limit(50)).all()
    else:
        linhas = sessao.execute(consulta.where(AtividadeTarefa.concluida_em.is_(None)).order_by(AtividadeTarefa.prazo, AtividadeTarefa.criada_em)).all()
    return [(a, t) for a, t in linhas if servico.pode_ver(sessao, usuario, t)]


def lembrar(sessao: Session, dia: date | None = None) -> dict[str, int]:
    """Rotina das 07:00: avisa as atividades de hoje e as atrasadas (uma vez por dia)."""
    dia = dia or hoje_sao_paulo()
    contagem = {"hoje": 0, "atrasadas": 0}
    for atividade, tarefa in sessao.execute(select(AtividadeTarefa, Tarefa).join(Tarefa, Tarefa.id == AtividadeTarefa.tarefa_id)
                                             .where(AtividadeTarefa.concluida_em.is_(None), AtividadeTarefa.prazo <= dia)).all():
        if atividade.responsavel_id is None:
            continue
        atrasada = atividade.prazo < dia
        quem = {atividade.responsavel_id} | ({atividade.criada_por_id} - {None, atividade.responsavel_id} if atrasada else set())
        servico._avisar(
            sessao, quem, f"{'Atividade atrasada' if atrasada else 'Atividade para hoje'}: {atividade.resumo}",
            f"{ROTULOS_TIPO[atividade.tipo]} da tarefa {servico._rotulo(tarefa)}, prazo {atividade.prazo:%d/%m/%Y}.", tarefa,
            f"tarefa-atividade-lembrete:{atividade.id}:{dia}", categoria="prazo", prioridade="alta" if atrasada else "normal",
        )
        contagem["atrasadas" if atrasada else "hoje"] += 1
    sessao.commit()
    return contagem


def seguir(sessao: Session, usuario: Usuario, tarefa: Tarefa, seguir_agora: bool) -> Tarefa:
    atual = sessao.get(SeguidorTarefa, (tarefa.id, usuario.id))
    if seguir_agora and atual is None:
        sessao.add(SeguidorTarefa(tarefa_id=tarefa.id, usuario_id=usuario.id))
    elif not seguir_agora and atual is not None:
        sessao.delete(atual)
    sessao.commit()
    return tarefa
