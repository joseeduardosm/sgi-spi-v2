# Criado por José Eduardo Santana Martins
# Este arquivo serve para manter o setor sistêmico "Equipes de contratos" com quem integra a equipe de algum contrato.
"""Setor sistêmico "Equipes de contratos", mantido pelo sistema.

Todo usuário ativo com designação **vigente** na equipe de ao menos um contrato (gestor, fiscais etc.) é membro; quem deixa de integrar a
equipe de todos os contratos (troca de designado, designação encerrada, contrato excluído ou usuário inativado) sai. Ninguém edita a
lista à mão: a cada alteração da equipe (`servico_contratos`) a lista é recalculada na mesma transação.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratos import Contrato, DesignacaoEquipe
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario

NOME_SETOR = "Equipes de contratos"


def obter_setor(sessao: Session) -> Setor:
    """O setor sistêmico (criado na primeira vez, caso a migração ainda não o tenha criado)."""
    setor = sessao.scalar(select(Setor).where(Setor.nome == NOME_SETOR, Setor.sistemico.is_(True)))
    if setor is None:
        setor = Setor(nome=NOME_SETOR, sistemico=True, ativo=True)
        sessao.add(setor)
        sessao.flush()
    return setor


def usuarios_das_equipes(sessao: Session) -> set[int]:
    """Usuários ativos com designação vigente na equipe de algum contrato."""
    agora = agora_utc()
    consulta = (
        select(DesignacaoEquipe.usuario_id).join(Contrato, Contrato.id == DesignacaoEquipe.contrato_id)
        .join(Usuario, Usuario.id == DesignacaoEquipe.usuario_id)
        .where(Usuario.ativo.is_(True),
               (DesignacaoEquipe.valido_de.is_(None)) | (DesignacaoEquipe.valido_de <= agora),
               (DesignacaoEquipe.valido_ate.is_(None)) | (DesignacaoEquipe.valido_ate > agora))
    )
    return set(sessao.scalars(consulta))


def sincronizar(sessao: Session) -> None:
    """Recalcula os membros do setor (entram os que passaram a integrar uma equipe; saem os que não integram mais nenhuma).

    Não faz commit: roda na transação de quem alterou a equipe.
    """
    sessao.flush()
    setor = obter_setor(sessao)
    desejados = usuarios_das_equipes(sessao)
    atuais = {m.usuario_id: m for m in sessao.scalars(select(MembroSetor).where(MembroSetor.setor_id == setor.id))}
    for usuario_id, membro in atuais.items():
        if usuario_id not in desejados:
            sessao.delete(membro)
    for usuario_id in desejados - set(atuais):
        sessao.add(MembroSetor(setor_id=setor.id, usuario_id=usuario_id))
    sessao.flush()
