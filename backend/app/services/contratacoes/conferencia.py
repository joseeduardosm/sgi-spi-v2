# Criado por José Eduardo Santana Martins
# Este arquivo serve para a conferência antes de concluir um documento e para o andamento (painel e avisos de revisão parada).
"""Conferência e andamento de Contratações."""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.models.contratacoes import DocumentoContratacao, ItemContratacao, RevisaoItem, SecaoContratacao
from app.services import servico_mensagens
from app.services.contratacoes import revisoes


def conferir(documento: DocumentoContratacao) -> dict:
    """Pendências antes de concluir. `bloqueios` impedem concluir; `alertas` pedem atenção (o usuário pode concluir mesmo assim)."""
    alertas: list[str] = []
    bloqueios: list[str] = []
    vazias = [s.titulo for s in documento.secoes if not s.itens]
    if not documento.secoes:
        alertas.append("O documento ainda não tem seções.")
    if vazias:
        alertas.append(f"{len(vazias)} seção(ões) sem itens: {', '.join(vazias[:5])}{'…' if len(vazias) > 5 else ''}.")
    marcados = [i for s in documento.secoes for i in s.itens if i.precisa_revisao]
    if marcados:
        alertas.append(f"{len(marcados)} item(ns) marcado(s) como \"precisa de revisão\".")
    propostas = [r for r in revisoes.abertas(documento) if r.conteudo_proposto or r.conteudo_proposto_html]
    if propostas:
        bloqueios.append(f"{len(propostas)} proposta(s) de alteração ainda não aplicada(s) nem resolvida(s).")
    comentarios = [r for r in revisoes.abertas(documento) if not (r.conteudo_proposto or r.conteudo_proposto_html)]
    if comentarios:
        alertas.append(f"{len(comentarios)} comentário(s) de revisão não resolvido(s).")
    if not documento.processo.strip():
        alertas.append("O número do processo SEI não foi informado.")
    return {"pode_concluir": not bloqueios, "bloqueios": bloqueios, "alertas": alertas}


def painel(sessao: Session, consulta) -> dict:
    """Totais por situação e por tipo dos documentos da consulta, e quantas revisões abertas há."""
    docs = list(sessao.scalars(consulta.options(selectinload(DocumentoContratacao.secoes).selectinload(SecaoContratacao.itens).selectinload(ItemContratacao.revisoes))))
    return {
        "total": len(docs),
        "por_situacao": {s: sum(1 for d in docs if d.situacao == s) for s in ("rascunho", "em_revisao", "concluido")},
        "por_tipo": {t: sum(1 for d in docs if d.tipo == t) for t in ("etp", "tr")},
        "revisoes_abertas": sum(len(revisoes.abertas(d)) for d in docs),
        "sem_vinculo": sum(1 for d in docs if d.contrato_id is None and d.situacao == "concluido"),
    }


def lembrar_revisoes_paradas(sessao: Session, dia: date | None = None) -> int:
    """Revisões abertas há `contratacoes_dias_aviso` dias (e de novo ao dobro): aviso com e-mail ao criador do documento."""
    dias = obter_configuracao().contratacoes_dias_aviso
    agora = agora_utc()
    avisados = 0
    abertas = sessao.scalars(select(RevisaoItem).where(RevisaoItem.resolvida_em.is_(None), RevisaoItem.aplicada_em.is_(None)).options(
        selectinload(RevisaoItem.item).selectinload(ItemContratacao.secao).selectinload(SecaoContratacao.documento)))
    for r in abertas:
        criada: datetime = r.criada_em if r.criada_em.tzinfo else r.criada_em.replace(tzinfo=agora.tzinfo)
        idade = (agora - criada).days
        marco = 2 if idade >= 2 * dias else 1 if idade >= dias else 0
        documento = r.item.secao.documento
        if not marco or documento.criador_id is None:
            continue
        if servico_mensagens.notificar(
            sessao, [documento.criador_id], f"Revisão parada em «{documento.nome}»",
            f"Há uma {'proposta de alteração' if r.conteudo_proposto else 'revisão'} de {r.autor_nome} sem resposta há {idade} dias em “{documento.nome}”.",
            chave=f"contratacao-revisao:{r.id}:parada{marco}", categoria="pendencia", prioridade="normal", link=f"/contratacoes/{documento.id}", email=True,
        ):
            avisados += 1
    sessao.commit()
    return avisados
