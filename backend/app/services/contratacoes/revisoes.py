# Criado por José Eduardo Santana Martins
# Este arquivo serve para as revisões dos itens: comentário, proposta de alteração, aplicação e resolução, com aviso ao autor do documento.
"""Revisões de Contratações.

Qualquer participante comenta e propõe (revisor, editor, criador). **Aplicam** a proposta o criador e os editores (no app antigo só o
criador). Aplicar copia a proposta para o item, registra quem aplicou e gera uma versão; o histórico do item guarda o antes e o depois.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratacoes import DocumentoContratacao, ItemContratacao, RevisaoItem
from app.models.usuario import Usuario
from app.services import servico_mensagens
from app.services.contratacoes import arvore, conteudo, versoes
from app.services.contratacoes.acesso import ErroContratacao
from app.services.servico_auditoria import auditar


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


def _destinatarios(documento: DocumentoContratacao, autor: Usuario) -> list[int]:
    """Quem acompanha o documento: o criador e os editores (menos quem agiu)."""
    ids = {documento.criador_id, *(m.usuario_id for m in documento.membros if m.papel == "editor")}
    ids.discard(autor.id)
    return [i for i in ids if i is not None]


def criar(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, comentario: str, texto: str | None, html: str | None, autor: Usuario) -> RevisaoItem:
    item = arvore.carregar_item(sessao, documento, item_id)
    comentario = (comentario or "").strip()
    if not comentario:
        raise ErroContratacao("O comentário da revisão é obrigatório.")
    proposto = proposto_html = None
    if (texto and texto.strip()) or (html and html.strip()):
        try:
            proposto, proposto_html = conteudo.normalizar(texto, html)
        except conteudo.ErroConteudo as erro:
            raise ErroContratacao(str(erro)) from erro
    revisao = RevisaoItem(item_id=item.id, autor_id=autor.id, autor_nome=_nome(autor), comentario=comentario[:4000], conteudo_original=item.conteudo,
                          conteudo_original_html=item.conteudo_html, conteudo_proposto=proposto, conteudo_proposto_html=proposto_html)
    item.revisoes.append(revisao)
    sessao.flush()
    # Com revisão aberta, o documento passa a "em revisão" (se ainda era rascunho)
    if documento.situacao == "rascunho":
        documento.situacao = "em_revisao"
    documento.atualizado_em = agora_utc()
    servico_mensagens.notificar(
        sessao, _destinatarios(documento, autor), "Nova proposta de alteração" if proposto else "Novo comentário em documento",
        f"{_nome(autor)} registrou uma {'proposta de alteração' if proposto else 'revisão'} em “{documento.nome}”.\n\n{comentario[:300]}",
        chave=f"contratacao-revisao:{revisao.id}:criada", categoria="comunicado", link=f"/contratacoes/{documento.id}", email=True, autor=autor,
    )
    auditar(sessao, autor.login, "contratacao.revisao.proposta" if proposto else "contratacao.revisao.comentario", documento.nome, autor_id=autor.id,
            alvo_tipo="contratacao", alvo_id=documento.id, dados={"item": str(item.id)})
    sessao.commit()
    return revisao


def _carregar(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, revisao_id: uuid.UUID) -> tuple[ItemContratacao, RevisaoItem]:
    item = arvore.carregar_item(sessao, documento, item_id)
    revisao = sessao.get(RevisaoItem, revisao_id)
    if revisao is None or revisao.item_id != item.id:
        raise ErroContratacao("Revisão não encontrada.", 404, "nao_encontrado")
    return item, revisao


def aplicar(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, revisao_id: uuid.UUID, autor: Usuario) -> RevisaoItem:
    item, revisao = _carregar(sessao, documento, item_id, revisao_id)
    if not (revisao.conteudo_proposto or revisao.conteudo_proposto_html):
        raise ErroContratacao("Esta revisão não possui proposta de alteração.")
    if revisao.aplicada_em is not None:
        raise ErroContratacao("Esta proposta já foi aplicada.", 409, "conflito")
    # O estado de antes fica numa versão própria; o item guarda o antes e o depois no histórico
    versoes.antes_da_edicao(sessao, documento, autor)
    versoes.registrar(sessao, documento, "sessao", autor, "Estado antes de aplicar uma proposta")
    antes = item.conteudo_html or item.conteudo
    item.conteudo, item.conteudo_html = conteudo.normalizar(revisao.conteudo_proposto, revisao.conteudo_proposto_html)
    versoes.historico(sessao, documento, item.id, "editou", antes, item.conteudo_html or item.conteudo, autor, f"Proposta de {revisao.autor_nome} aplicada")
    revisao.aplicada_em, revisao.aplicada_por_id, revisao.aplicada_por_nome = agora_utc(), autor.id, _nome(autor)
    revisao.resolvida_em, revisao.resolvida_por_nome = revisao.aplicada_em, _nome(autor)
    documento.atualizado_por_id, documento.atualizado_em = autor.id, agora_utc()
    sessao.flush()
    versoes.registrar(sessao, documento, "proposta", autor, f"Proposta de {revisao.autor_nome} aplicada")
    if revisao.autor_id and revisao.autor_id != autor.id:
        servico_mensagens.notificar(
            sessao, [revisao.autor_id], "Proposta de alteração aplicada", f"{_nome(autor)} aplicou a sua proposta em “{documento.nome}”.",
            chave=f"contratacao-revisao:{revisao.id}:aplicada", categoria="comunicado", link=f"/contratacoes/{documento.id}", email=True, autor=autor,
        )
    servico_mensagens.encerrar(sessao, chave=f"contratacao-revisao:{revisao.id}:criada")
    auditar(sessao, autor.login, "contratacao.revisao.aplicar", documento.nome, autor_id=autor.id, alvo_tipo="contratacao", alvo_id=documento.id, dados={"item": str(item.id)})
    sessao.commit()
    return revisao


def resolver(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, revisao_id: uuid.UUID, resolvida: bool, autor: Usuario) -> RevisaoItem:
    """Marca a revisão como resolvida (ou volta a aberta). Qualquer participante resolve o comentário; proposta aplicada já está resolvida."""
    _, revisao = _carregar(sessao, documento, item_id, revisao_id)
    if revisao.aplicada_em is not None and not resolvida:
        raise ErroContratacao("Uma proposta aplicada não volta a ficar aberta.", 409, "conflito")
    revisao.resolvida_em, revisao.resolvida_por_nome = (agora_utc(), _nome(autor)) if resolvida else (None, None)
    if resolvida:
        servico_mensagens.encerrar(sessao, chave=f"contratacao-revisao:{revisao.id}:criada")
    sessao.commit()
    return revisao


def abertas(documento: DocumentoContratacao) -> list[RevisaoItem]:
    return [r for s in documento.secoes for i in s.itens for r in i.revisoes if r.resolvida_em is None]
