# Criado por José Eduardo Santana Martins
# Este arquivo serve para registrar, listar, comparar e restaurar as versões do documento e o histórico de cada item.
"""Versionamento do documento (estilo BookStack, mas por item).

- **Versão** (`VersaoDocumento`): a *foto* completa da árvore em um marco. Nasce na criação, na importação, na mudança de situação, na
  aplicação de proposta, na restauração, na migração e a pedido (com resumo); e **antes da primeira edição de uma sessão** (sem edição
  há `CONTRATACOES_SESSAO_MINUTOS`), de modo que o que for retirado nunca se perde.
- **Histórico do item** (`HistoricoItem`): uma linha por edição (antes e depois), automática, que sobrevive à exclusão do item.
- **Restaurar** uma versão recria a árvore (mantendo os ids que ainda existem) e gera uma nova versão; **restaurar um item** volta só
  o conteúdo dele a um estado do histórico.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.banco import em_sao_paulo
from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.models.contratacoes import (
    DocumentoContratacao, HistoricoItem, ItemContratacao, LinhaTabelaTr, SecaoContratacao, VersaoDocumento,
)
from app.models.usuario import Usuario
from app.services.contratacoes import diferencas
from app.services.contratacoes.acesso import ErroContratacao

ROTULOS_TIPO = {"criacao": "Criação", "manual": "Versão salva", "importacao": "Importação do Word", "situacao": "Mudança de situação",
                "proposta": "Proposta aplicada", "restauracao": "Restauração", "migracao": "Migrado do SGI", "sessao": "Antes de uma edição"}


def _nome(usuario: Usuario | None) -> str:
    return (usuario.nome_completo or usuario.login) if usuario else "Sistema"


def foto(documento: DocumentoContratacao) -> dict:
    """Retrato do documento: metadados, seções, itens (com `secao_id`/`pai_id`) e linhas da tabela do TR, em ordem estável."""
    secoes = sorted(documento.secoes, key=lambda s: s.ordem)
    itens: list[dict] = []
    linhas: list[dict] = []
    for secao in secoes:
        for i in sorted(secao.itens, key=lambda x: (x.pai_id is not None, str(x.pai_id or ""), x.ordem)):
            itens.append({"id": str(i.id), "secao_id": str(secao.id), "pai_id": str(i.pai_id) if i.pai_id else None, "tipo": i.tipo, "ordem": i.ordem,
                          "conteudo": i.conteudo, "conteudo_html": i.conteudo_html, "precisa_revisao": i.precisa_revisao})
            linhas += [{"id": str(l.id), "item_id": str(i.id), "ordem": l.ordem, "descricao": l.descricao, "siafisico": l.siafisico, "catser_catmat": l.catser_catmat,
                        "unidade": l.unidade, "quantidade_mensal": str(l.quantidade_mensal), "quantidade_objeto": str(l.quantidade_objeto)} for l in i.linhas_tabela]
    return {"nome": documento.nome, "processo": documento.processo, "link_sei": documento.link_sei or "", "situacao": documento.situacao,
            "secoes": [{"id": str(s.id), "ordem": s.ordem, "titulo": s.titulo} for s in secoes], "itens": itens, "linhas_tabela": linhas}


def _hash(f: dict) -> str:
    return hashlib.sha256(json.dumps(f, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def ultima_versao(sessao: Session, documento: DocumentoContratacao) -> VersaoDocumento | None:
    return sessao.scalar(select(VersaoDocumento).where(VersaoDocumento.documento_id == documento.id).order_by(VersaoDocumento.numero.desc()).limit(1))


def registrar(sessao: Session, documento: DocumentoContratacao, tipo: str, autor: Usuario | None, resumo: str = "") -> VersaoDocumento | None:
    """Grava uma versão com a foto atual. Versão automática de sessão não se repete se nada mudou desde a última."""
    sessao.flush()
    sessao.refresh(documento)
    f = foto(documento)
    h = _hash(f)
    anterior = ultima_versao(sessao, documento)
    if tipo == "sessao" and anterior is not None and anterior.hash == h:
        return None
    numero = (anterior.numero if anterior else 0) + 1
    versao = VersaoDocumento(documento_id=documento.id, numero=numero, tipo=tipo, resumo=(resumo or "").strip()[:500], autor_id=autor.id if autor else None,
                             autor_nome=_nome(autor), foto=f, hash=h, criada_em=agora_utc())
    sessao.add(versao)
    sessao.flush()
    _aparar(sessao, documento)
    return versao


def _aparar(sessao: Session, documento: DocumentoContratacao) -> None:
    """Respeita o limite de versões: remove as mais antigas **automáticas** (sessão, proposta, restauração); marcos ficam."""
    limite = obter_configuracao().contratacoes_limite_versoes
    total = sessao.scalar(select(func.count(VersaoDocumento.id)).where(VersaoDocumento.documento_id == documento.id)) or 0
    if total <= limite:
        return
    antigas = list(sessao.scalars(select(VersaoDocumento.id).where(
        VersaoDocumento.documento_id == documento.id, VersaoDocumento.tipo.in_(("sessao", "proposta", "restauracao"))).order_by(VersaoDocumento.numero).limit(total - limite)))
    if antigas:
        sessao.execute(delete(VersaoDocumento).where(VersaoDocumento.id.in_(antigas)))


def antes_da_edicao(sessao: Session, documento: DocumentoContratacao, autor: Usuario) -> None:
    """Primeira edição depois de uma pausa: guarda o estado de antes (versão `sessao`) e marca o instante da edição."""
    agora = agora_utc()
    ultima = documento.ultima_edicao_em
    if ultima is not None and ultima.tzinfo is None:
        ultima = ultima.replace(tzinfo=agora.tzinfo)
    if ultima is None or agora - ultima > timedelta(minutes=obter_configuracao().contratacoes_sessao_minutos):
        registrar(sessao, documento, "sessao", autor, "Estado antes de uma nova sessão de edição")
    documento.ultima_edicao_em = agora


def historico(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, mudanca: str, antes: str | None, depois: str | None, autor: Usuario | None,
              detalhe: str = "") -> None:
    sessao.add(HistoricoItem(documento_id=documento.id, item_id=item_id, mudanca=mudanca, antes_html=antes, depois_html=depois, detalhe=detalhe[:300],
                             autor_id=autor.id if autor else None, autor_nome=_nome(autor), ocorrido_em=agora_utc()))


# --- Consultas ----------------------------------------------------------------------------------

def listar(sessao: Session, documento: DocumentoContratacao) -> list[VersaoDocumento]:
    return list(sessao.scalars(select(VersaoDocumento).where(VersaoDocumento.documento_id == documento.id).order_by(VersaoDocumento.numero.desc())))


def obter(sessao: Session, documento: DocumentoContratacao, numero: int) -> VersaoDocumento:
    versao = sessao.scalar(select(VersaoDocumento).where(VersaoDocumento.documento_id == documento.id, VersaoDocumento.numero == numero))
    if versao is None:
        raise ErroContratacao("Versão não encontrada.", 404, "nao_encontrado")
    return versao


def alteracoes(sessao: Session, documento: DocumentoContratacao, numero: int, contra: int | None = None) -> dict:
    """O que mudou na versão `numero` em relação à anterior (ou a `contra`); a versão 1 compara com um documento vazio."""
    versao = obter(sessao, documento, numero)
    if contra is not None:
        base = obter(sessao, documento, contra).foto
    else:
        anterior = sessao.scalar(select(VersaoDocumento).where(VersaoDocumento.documento_id == documento.id, VersaoDocumento.numero < numero)
                                 .order_by(VersaoDocumento.numero.desc()).limit(1))
        base = anterior.foto if anterior else diferencas.vazio()
    return {"versao": versao.numero, "contra": contra if contra is not None else (versao.numero - 1 if base is not diferencas.vazio() and numero > 1 else None), **diferencas.comparar(base, versao.foto)}


def historico_do_item(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID) -> list[dict]:
    """Edições do item, da mais recente para a mais antiga, cada uma com a diferença por palavra."""
    linhas = list(sessao.scalars(select(HistoricoItem).where(HistoricoItem.documento_id == documento.id, HistoricoItem.item_id == item_id).order_by(HistoricoItem.ocorrido_em.desc())))
    return [{"id": h.id, "mudanca": h.mudanca, "autor_nome": h.autor_nome, "ocorrido_em": h.ocorrido_em, "detalhe": h.detalhe, "antes_html": h.antes_html, "depois_html": h.depois_html,
             "diferenca": diferencas.diferenca_html(h.antes_html, h.depois_html) if h.mudanca in ("editou", "restaurou") else ""} for h in linhas]


# --- Restauração -------------------------------------------------------------------------------

def restaurar_versao(sessao: Session, documento: DocumentoContratacao, numero: int, autor: Usuario) -> VersaoDocumento:
    """Volta a árvore ao estado da versão (mantendo os ids que ainda existem) e registra uma nova versão. O estado atual é guardado antes."""
    versao = obter(sessao, documento, numero)
    registrar(sessao, documento, "sessao", autor, f"Estado antes de restaurar a versão {numero}")
    f = versao.foto
    secoes_foto = {s["id"]: s for s in f["secoes"]}
    itens_foto = {i["id"]: i for i in f["itens"]}
    atuais_secoes = {str(s.id): s for s in documento.secoes}
    atuais_itens = {str(i.id): i for s in documento.secoes for i in s.itens}

    # Itens e seções que não existem na versão saem (com histórico "removeu")
    for item_id, item in atuais_itens.items():
        if item_id not in itens_foto:
            historico(sessao, documento, item.id, "removeu", item.conteudo_html or item.conteudo, None, autor, f"Removido ao restaurar a versão {numero}")
    for secao_id, secao in atuais_secoes.items():
        if secao_id not in secoes_foto:
            sessao.delete(secao)
    sessao.flush()
    sessao.expire(documento)
    atuais_secoes = {str(s.id): s for s in documento.secoes}
    atuais_itens = {str(i.id): i for s in documento.secoes for i in s.itens}

    for sid, s in secoes_foto.items():
        secao = atuais_secoes.get(sid)
        if secao is None:
            secao = SecaoContratacao(id=uuid.UUID(sid), documento_id=documento.id, ordem=s["ordem"], titulo=s["titulo"])
            sessao.add(secao)
        else:
            secao.ordem, secao.titulo = s["ordem"], s["titulo"]
    sessao.flush()
    # Pais antes dos filhos: cria/atualiza em ordem de profundidade
    def profundidade(i: dict) -> int:
        n, atual = 0, i
        while atual.get("pai_id"):
            atual, n = itens_foto[atual["pai_id"]], n + 1
        return n

    for i in sorted(itens_foto.values(), key=profundidade):
        existente = atuais_itens.get(i["id"])
        if existente is None:
            sessao.add(ItemContratacao(id=uuid.UUID(i["id"]), secao_id=uuid.UUID(i["secao_id"]), pai_id=uuid.UUID(i["pai_id"]) if i["pai_id"] else None, tipo=i["tipo"],
                                       ordem=i["ordem"], conteudo=i["conteudo"], conteudo_html=i["conteudo_html"], precisa_revisao=i["precisa_revisao"]))
            historico(sessao, documento, uuid.UUID(i["id"]), "restaurou", None, i["conteudo_html"] or i["conteudo"], autor, f"Recriado ao restaurar a versão {numero}")
        else:
            if (existente.conteudo_html or existente.conteudo) != (i["conteudo_html"] or i["conteudo"]):
                historico(sessao, documento, existente.id, "restaurou", existente.conteudo_html or existente.conteudo, i["conteudo_html"] or i["conteudo"], autor,
                          f"Conteúdo da versão {numero}")
            existente.secao_id, existente.pai_id, existente.tipo, existente.ordem = uuid.UUID(i["secao_id"]), (uuid.UUID(i["pai_id"]) if i["pai_id"] else None), i["tipo"], i["ordem"]
            existente.conteudo, existente.conteudo_html, existente.precisa_revisao = i["conteudo"], i["conteudo_html"], i["precisa_revisao"]
        sessao.flush()
    # Tabela do TR
    sessao.execute(delete(LinhaTabelaTr).where(LinhaTabelaTr.item_id.in_([uuid.UUID(i) for i in itens_foto])))
    for l in f.get("linhas_tabela", []):
        sessao.add(LinhaTabelaTr(id=uuid.UUID(l["id"]), item_id=uuid.UUID(l["item_id"]), ordem=l["ordem"], descricao=l["descricao"], siafisico=l["siafisico"],
                                 catser_catmat=l["catser_catmat"], unidade=l["unidade"], quantidade_mensal=l["quantidade_mensal"], quantidade_objeto=l["quantidade_objeto"]))
    documento.nome, documento.processo, documento.link_sei = f["nome"], f["processo"], f["link_sei"] or None
    documento.atualizado_por_id, documento.ultima_edicao_em = autor.id, agora_utc()
    sessao.flush()
    sessao.expire(documento)
    return registrar(sessao, documento, "restauracao", autor, f"Restaurou a versão {numero}")  # type: ignore[return-value]


def restaurar_item(sessao: Session, documento: DocumentoContratacao, historico_id: uuid.UUID, estado: str, autor: Usuario) -> ItemContratacao:
    """Volta só o conteúdo de um item ao `antes` ou `depois` de uma edição do histórico (o item precisa existir)."""
    entrada = sessao.get(HistoricoItem, historico_id)
    if entrada is None or entrada.documento_id != documento.id:
        raise ErroContratacao("Registro do histórico não encontrado.", 404, "nao_encontrado")
    item = sessao.get(ItemContratacao, entrada.item_id)
    if item is None:
        raise ErroContratacao("O item não existe mais: restaure a versão do documento para recuperá-lo.", 409, "conflito")
    from app.services.contratacoes import conteudo

    alvo = entrada.antes_html if estado == "antes" else entrada.depois_html
    if alvo is None:
        raise ErroContratacao("Não há conteúdo nesse estado do histórico.", 409, "conflito")
    antes_da_edicao(sessao, documento, autor)
    anterior = item.conteudo_html or item.conteudo
    item.conteudo, item.conteudo_html = conteudo.normalizar(None, alvo)
    historico(sessao, documento, item.id, "restaurou", anterior, item.conteudo_html or item.conteudo, autor, f"Voltou ao estado {'anterior' if estado == 'antes' else 'posterior'} de uma edição de {em_sao_paulo(entrada.ocorrido_em):%d/%m/%Y %H:%M}")
    documento.atualizado_por_id = autor.id
    return item
