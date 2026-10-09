# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras dos estágios (colunas) configuráveis das equipes de tarefas.
"""Estágios por equipe.

Cada estágio pertence a uma das 4 **categorias** do pipeline (a fazer, em andamento, em validação, concluída): as regras de quem pode validar,
os avisos, o burndown e os relatórios continuam seguindo a categoria. Regras da configuração:
- as categorias seguem a ordem do pipeline (todos os "a fazer", depois os "em andamento", depois "em validação" e por fim "concluída");
- ao menos um estágio de "a fazer" e de "em andamento", e **exatamente um** de "em validação" e de "concluída";
- nomes únicos na equipe; estágio com tarefas só é excluído depois de as tarefas serem movidas (`409`).
Mover entre estágios da mesma categoria só troca a coluna; mudar de categoria segue o pipeline (`servico_tarefas.mover`).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tarefas import EquipeTarefas, EstagioTarefa, STATUS_TAREFA, Tarefa
from app.models.usuario import Usuario
from app.services.servico_auditoria import auditar
from app.services.tarefas import servico_tarefas as servico
from app.services.tarefas.servico_tarefas import ErroTarefa

PADRAO = (("A fazer", "a_fazer", 0), ("Em andamento", "em_andamento", 4), ("Em validação", "em_validacao", 5), ("Concluída", "concluida", 10))


@dataclass
class DadosEstagio:
    nome: str
    categoria: str
    cor_indice: int = 0
    id: uuid.UUID | None = None


def pode_ver(sessao: Session, usuario: Usuario, equipe: EquipeTarefas) -> bool:
    return usuario.superusuario or usuario.id in servico.lideranca(sessao, equipe) or usuario.id in servico.membros(equipe)


def listar(sessao: Session, usuario: Usuario, equipe_id: uuid.UUID) -> list[EstagioTarefa]:
    """Estágios da equipe em ordem; uma equipe sem estágios ganha os 4 padrão na primeira consulta."""
    equipe = sessao.get(EquipeTarefas, equipe_id)
    if equipe is None or not pode_ver(sessao, usuario, equipe):
        raise ErroTarefa("Equipe não encontrada.", 404, "nao_encontrado")
    estagios = _da_equipe(sessao, equipe_id)
    if not estagios:
        for posicao, (nome, categoria, cor) in enumerate(PADRAO):
            sessao.add(EstagioTarefa(equipe_id=equipe_id, nome=nome, posicao=posicao, categoria=categoria, cor_indice=cor))
        sessao.commit()
        estagios = _da_equipe(sessao, equipe_id)
    return estagios


def _da_equipe(sessao: Session, equipe_id: uuid.UUID) -> list[EstagioTarefa]:
    return list(sessao.scalars(select(EstagioTarefa).where(EstagioTarefa.equipe_id == equipe_id).order_by(EstagioTarefa.posicao)))


def _validar(itens: list[DadosEstagio]) -> None:
    if not 4 <= len(itens) <= 20:
        raise ErroTarefa("A equipe precisa de 4 a 20 estágios.")
    nomes = [i.nome.strip().lower() for i in itens]
    if any(not n for n in nomes) or len(set(nomes)) != len(nomes):
        raise ErroTarefa("Cada estágio precisa de um nome, sem repetir nomes na equipe.")
    categorias = [i.categoria for i in itens]
    if any(c not in STATUS_TAREFA for c in categorias):
        raise ErroTarefa("Categoria de estágio inválida.")
    ordem = [STATUS_TAREFA.index(c) for c in categorias]
    if ordem != sorted(ordem):
        raise ErroTarefa("Os estágios precisam seguir a ordem do pipeline: A fazer, Em andamento, Em validação e Concluída.")
    for obrigatoria in ("a_fazer", "em_andamento"):
        if obrigatoria not in categorias:
            raise ErroTarefa("É preciso ter ao menos um estágio de \"A fazer\" e um de \"Em andamento\".")
    for unica in ("em_validacao", "concluida"):
        if categorias.count(unica) != 1:
            raise ErroTarefa("É preciso ter exatamente um estágio de \"Em validação\" e um de \"Concluída\".")
    if any(not 0 <= i.cor_indice <= 11 for i in itens):
        raise ErroTarefa("Cor de estágio inválida.")


def substituir(sessao: Session, autor: Usuario, equipe_id: uuid.UUID, itens: list[DadosEstagio]) -> list[EstagioTarefa]:
    """Grava a lista completa e ordenada de estágios (dono, liderança ou SuperRoot)."""
    equipe = sessao.get(EquipeTarefas, equipe_id)
    if equipe is None:
        raise ErroTarefa("Equipe não encontrada.", 404, "nao_encontrado")
    servico._exigir(autor.superusuario or autor.id in servico.lideranca(sessao, equipe), "Só a liderança da equipe configura os estágios.")
    _validar(itens)
    atuais = {e.id: e for e in _da_equipe(sessao, equipe_id)}
    mantidos = {i.id for i in itens if i.id}
    if mantidos - set(atuais):
        raise ErroTarefa("Estágio inexistente na equipe.")
    for removido in set(atuais) - mantidos:
        com_tarefas = sessao.scalar(select(func.count(Tarefa.id)).where(Tarefa.estagio_id == removido)) or 0
        if com_tarefas:
            raise ErroTarefa(f"O estágio \"{atuais[removido].nome}\" tem {com_tarefas} tarefa(s): mova-as antes de excluí-lo.", 409, "conflito")
    for removido in set(atuais) - mantidos:
        sessao.delete(atuais[removido])
    sessao.flush()
    for posicao, item in enumerate(itens):
        estagio = atuais.get(item.id) if item.id else EstagioTarefa(equipe_id=equipe_id)
        estagio.nome, estagio.categoria, estagio.cor_indice, estagio.posicao = item.nome.strip(), item.categoria, item.cor_indice, posicao
        sessao.add(estagio)
    auditar(sessao, autor.login, "tarefas.estagios", equipe.nome, f"{len(itens)} estágio(s)", autor_id=autor.id, alvo_tipo="tarefa-equipe", alvo_id=equipe.id)
    sessao.commit()
    return _da_equipe(sessao, equipe_id)


def definir_estagio(sessao: Session, autor: Usuario, tarefa: Tarefa, estagio_id: uuid.UUID, versao: int | None = None) -> Tarefa:
    """Troca a coluna da tarefa dentro da mesma categoria (para mudar de categoria, use o pipeline)."""
    servico._exigir_nao_concluida(tarefa, "mudar o estágio")
    servico.exigir_nao_controlada(tarefa, "mudar o estágio")
    servico._versao(tarefa, versao)
    servico._exigir(autor.id in servico.envolvidos(tarefa) or servico.pode_editar(sessao, autor, tarefa), "Você não pode mover esta tarefa.")
    estagio = sessao.get(EstagioTarefa, estagio_id)
    if tarefa.equipe_id is None or estagio is None or estagio.equipe_id != tarefa.equipe_id:
        raise ErroTarefa("Estágio inexistente nesta equipe.")
    if estagio.categoria != tarefa.status:
        raise ErroTarefa("Este estágio é de outra situação: mova a tarefa pelo pipeline (iniciar, entregar, validar…).")
    atual = sessao.get(EstagioTarefa, tarefa.estagio_id) if tarefa.estagio_id else None
    if atual is None or atual.id != estagio.id:
        servico._evento(sessao, tarefa, "editada", autor, f"Estágio: {atual.nome if atual else '—'} → {estagio.nome}", estagio_de=atual.nome if atual else None, estagio_para=estagio.nome)
        servico.registrar_nas_subtarefas(sessao, tarefa, autor, f"estágio {atual.nome if atual else '—'} → {estagio.nome}", estagio_de=atual.nome if atual else None, estagio_para=estagio.nome)
        tarefa.estagio_id = estagio.id
        tarefa.versao += 1
    sessao.commit()
    return tarefa
