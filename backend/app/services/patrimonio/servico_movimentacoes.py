# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras de movimentação de bens entre salas: solicitação, autorização, recebimento parcial e conclusão.
"""Movimentação.

Fluxo: **solicitação** (modificação) → **autorização** (controle total, nunca o próprio solicitante) → **recebimento** (controle total, bem a bem,
com mudança de local na hora) → **conclusão** (os que não chegaram ficam livres na origem). O solicitante pode **cancelar** enquanto pendente.
Uma movimentação pode reunir bens de origens diferentes com um único destino (mudança de sala inteira).
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.patrimonio import Bem, ItemMovimentacao, Localizacao, Movimentacao
from app.models.usuario import Usuario
from app.services.patrimonio import servico_bens, servico_localizacoes
from app.services.patrimonio.base import ErroPatrimonio, avisar, exigir_outra_pessoa, ids_controle_total, registrar_evento

STATUS = ("pendente", "autorizada", "concluida", "recusada", "cancelada")
CARGA = (selectinload(Movimentacao.itens).selectinload(ItemMovimentacao.bem), selectinload(Movimentacao.itens).selectinload(ItemMovimentacao.origem),
         selectinload(Movimentacao.destino), selectinload(Movimentacao.solicitante), selectinload(Movimentacao.decidido_por))


def obter(sessao: Session, movimentacao_id: uuid.UUID) -> Movimentacao:
    mov = sessao.scalar(select(Movimentacao).where(Movimentacao.id == movimentacao_id).options(*CARGA))
    if mov is None:
        raise ErroPatrimonio("Movimentação não encontrada.", 404, "nao_encontrado")
    return mov


def listar(
    sessao: Session, *, status: str | None = None, solicitante_id: int | None = None, de: date | None = None, ate: date | None = None,
    origem_id: uuid.UUID | None = None, destino_id: uuid.UUID | None = None,
) -> list[Movimentacao]:
    """Relatório por período, status, origem e destino (o mais recente primeiro)."""
    consulta = select(Movimentacao).options(*CARGA).order_by(Movimentacao.solicitada_em.desc())
    if status:
        consulta = consulta.where(Movimentacao.status == status)
    if solicitante_id:
        consulta = consulta.where(Movimentacao.solicitante_id == solicitante_id)
    if de:
        consulta = consulta.where(Movimentacao.solicitada_em >= datetime.combine(de, time.min, tzinfo=agora_utc().tzinfo))
    if ate:
        consulta = consulta.where(Movimentacao.solicitada_em <= datetime.combine(ate, time.max, tzinfo=agora_utc().tzinfo))
    if destino_id:
        consulta = consulta.where(Movimentacao.destino_id == destino_id)
    movimentacoes = list(sessao.scalars(consulta))
    if origem_id:
        movimentacoes = [m for m in movimentacoes if any(i.origem_id == origem_id for i in m.itens)]
    return movimentacoes


def solicitar(sessao: Session, bens_ids: list[uuid.UUID], destino_id: uuid.UUID, motivo: str, autor: Usuario, *, id_cliente: str | None = None,
              chapas: list[str] | None = None) -> tuple[Movimentacao, bool]:
    """Abre a solicitação. Devolve `(movimentacao, criada)`: `criada` é falsa quando o `id_cliente` já foi enviado (reenvio offline)."""
    if id_cliente:
        existente = sessao.scalar(select(Movimentacao.id).where(Movimentacao.id_cliente == id_cliente))
        if existente is not None:
            return obter(sessao, existente), False
    if not motivo or not motivo.strip():
        raise ErroPatrimonio("Informe o motivo da movimentação.")
    # As chapas lidas offline viram bens aqui; chapa desconhecida recusa o pedido todo (404)
    ids = list(dict.fromkeys([*bens_ids, *[servico_bens.obter_por_chapa(sessao, c).id for c in (chapas or [])]]))
    if not ids:
        raise ErroPatrimonio("Escolha ao menos um bem.")
    destino = servico_localizacoes.exigir_sala(sessao, destino_id)
    if destino.responsavel_id is None:
        raise ErroPatrimonio("A sala de destino ainda não tem setor e responsável.", 409, "sala_sem_responsavel")
    mov = Movimentacao(id=uuid.uuid4(), id_cliente=id_cliente, destino_id=destino.id, motivo=motivo.strip(), status="pendente", solicitante_id=autor.id)
    for bem_id in ids:
        bem = servico_bens.obter(sessao, bem_id)
        servico_bens.exigir_movimentavel(sessao, bem, destino)
        mov.itens.append(ItemMovimentacao(id=uuid.uuid4(), bem_id=bem.id, origem_id=bem.localizacao_id))
    sessao.add(mov)
    sessao.flush()
    avisar(sessao, ids_controle_total(sessao), "Movimentação de bens aguardando autorização",
           f"{autor.nome_completo or autor.login} pediu para levar {len(ids)} bem(ns) para a sala {destino.codigo}.", f"patrimonio-mov-{mov.id}", autor, f"/patrimonio/movimentacoes/{mov.id}", categoria="pendencia", evento="patrimonio.movimentacao_pendente")
    sessao.commit()
    return obter(sessao, mov.id), True


def _pendente(mov: Movimentacao) -> None:
    if mov.status != "pendente":
        raise ErroPatrimonio("A movimentação não está pendente.", 409, "conflito")


def autorizar(sessao: Session, movimentacao_id: uuid.UUID, autor: Usuario) -> Movimentacao:
    mov = obter(sessao, movimentacao_id)
    _pendente(mov)
    exigir_outra_pessoa(autor, mov.solicitante_id)
    mov.status, mov.decidido_por_id, mov.decidido_em = "autorizada", autor.id, agora_utc()
    avisar(sessao, [mov.solicitante_id] if mov.solicitante_id else [], "Movimentação autorizada",
           f"Sua movimentação para a sala {mov.destino.codigo} foi autorizada: aguarde o recebimento dos bens.", f"patrimonio-mov-aut-{mov.id}", autor, f"/patrimonio/movimentacoes/{mov.id}", evento="patrimonio.movimentacao_decidida")
    sessao.commit()
    return obter(sessao, mov.id)


def recusar(sessao: Session, movimentacao_id: uuid.UUID, motivo: str, autor: Usuario) -> Movimentacao:
    mov = obter(sessao, movimentacao_id)
    _pendente(mov)
    exigir_outra_pessoa(autor, mov.solicitante_id)
    if not motivo or not motivo.strip():
        raise ErroPatrimonio("A recusa exige motivo.")
    mov.status, mov.decidido_por_id, mov.decidido_em, mov.motivo_recusa = "recusada", autor.id, agora_utc(), motivo.strip()
    avisar(sessao, [mov.solicitante_id] if mov.solicitante_id else [], "Movimentação recusada", f"Motivo: {motivo.strip()}", f"patrimonio-mov-rec-{mov.id}", autor, f"/patrimonio/movimentacoes/{mov.id}", evento="patrimonio.movimentacao_decidida")
    sessao.commit()
    return obter(sessao, mov.id)


def cancelar(sessao: Session, movimentacao_id: uuid.UUID, autor: Usuario) -> Movimentacao:
    """O solicitante cancela enquanto a movimentação ainda está pendente."""
    mov = obter(sessao, movimentacao_id)
    _pendente(mov)
    if mov.solicitante_id != autor.id:
        raise ErroPatrimonio("Só quem solicitou cancela a movimentação.", 403, "acl_negado")
    mov.status = "cancelada"
    sessao.commit()
    return obter(sessao, mov.id)


def receber(sessao: Session, movimentacao_id: uuid.UUID, bem_id: uuid.UUID, autor: Usuario, *, origem: str | None = None) -> Movimentacao:
    """Confirma a chegada de um bem (leitura do código): ele muda de local na hora e os demais continuam na origem."""
    mov = obter(sessao, movimentacao_id)
    if mov.status != "autorizada":
        raise ErroPatrimonio("Só se recebe bens de uma movimentação autorizada.", 409, "conflito")
    item = next((i for i in mov.itens if i.bem_id == bem_id), None)
    if item is None:
        raise ErroPatrimonio("Este bem não faz parte da movimentação.", 404, "nao_encontrado")
    if item.recebido_em is not None:
        raise ErroPatrimonio("Este bem já foi recebido.", 409, "conflito")
    bem = servico_bens.obter(sessao, bem_id)
    if bem.situacao in ("extraviado", "baixado") or bem.classificacao_pendente:
        raise ErroPatrimonio(f"O bem {bem.rotulo} não pode mais ser movimentado.", 409, "bem_bloqueado")
    servico_bens.mover_para(
        sessao, bem, mov.destino, autor, "moveu", f"Movimentação: {mov.motivo}", origem=origem,
        dados={"movimentacao_id": str(mov.id), "solicitante": mov.solicitante.login if mov.solicitante else None, "autorizador": mov.decidido_por.login if mov.decidido_por else None,
               "recebedor": autor.login})
    item.recebido_em, item.recebido_por_id = agora_utc(), autor.id
    # Todos recebidos: conclui sozinha
    if all(i.recebido_em is not None for i in mov.itens):
        _concluir(sessao, mov, autor, origem)
    sessao.commit()
    return obter(sessao, mov.id)


def _concluir(sessao: Session, mov: Movimentacao, autor: Usuario, origem: str | None) -> None:
    mov.status, mov.concluida_em = "concluida", agora_utc()
    for item in mov.itens:
        if item.recebido_em is None:
            bem = servico_bens.obter(sessao, item.bem_id)
            registrar_evento(sessao, bem, "nao_chegou", autor, texto=f"Não chegou ao destino {mov.destino.codigo}: permaneceu em {item.origem.codigo}", origem=origem,
                             dados={"movimentacao_id": str(mov.id), "destino": mov.destino.codigo, "origem": item.origem.codigo})
    avisar(sessao, [mov.solicitante_id] if mov.solicitante_id else [], "Movimentação concluída",
           f"{sum(1 for i in mov.itens if i.recebido_em)} de {len(mov.itens)} bem(ns) chegaram à sala {mov.destino.codigo}.", f"patrimonio-mov-fim-{mov.id}", autor, f"/patrimonio/movimentacoes/{mov.id}", evento="patrimonio.movimentacao_decidida")


def concluir(sessao: Session, movimentacao_id: uuid.UUID, autor: Usuario, *, origem: str | None = None) -> Movimentacao:
    """Encerra o recebimento: os bens que chegaram ficam no destino e os que não chegaram ficam livres para outra movimentação."""
    mov = obter(sessao, movimentacao_id)
    if mov.status != "autorizada":
        raise ErroPatrimonio("Só se conclui uma movimentação autorizada.", 409, "conflito")
    _concluir(sessao, mov, autor, origem)
    sessao.commit()
    return obter(sessao, mov.id)
