# Criado por José Eduardo Santana Martins
# Este arquivo serve para as operações sobre o documento e a árvore de seções e itens (criar, editar, mover, duplicar, excluir).
"""Documento e árvore de Contratações.

Toda mudança de conteúdo passa por `versoes.antes_da_edicao` (a versão automática de antes da sessão) e grava o `HistoricoItem` do
item. A ordem dos irmãos é normalizada (1, 2, 3…, sem lacunas) depois de inclusões, exclusões e movimentos.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratacoes import DocumentoContratacao, ItemContratacao, LinhaTabelaTr, MembroDocumento, SecaoContratacao
from app.models.usuario import Usuario
from app.services.contratacoes import conteudo, versoes
from app.services.contratacoes.acesso import ErroContratacao
from app.services.servico_auditoria import auditar

TIPOS_ITEM = ("item", "subitem", "inciso", "alinea", "subsecao")
MAXIMO_NIVEL = 12


def _tocar(documento: DocumentoContratacao, autor: Usuario) -> None:
    documento.atualizado_por_id, documento.atualizado_em = autor.id, agora_utc()


def _carregar_secao(sessao: Session, documento: DocumentoContratacao, secao_id: uuid.UUID) -> SecaoContratacao:
    secao = sessao.get(SecaoContratacao, secao_id)
    if secao is None or secao.documento_id != documento.id:
        raise ErroContratacao("Seção não encontrada.", 404, "nao_encontrado")
    return secao


def carregar_item(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID) -> ItemContratacao:
    item = sessao.get(ItemContratacao, item_id)
    if item is None or item.secao.documento_id != documento.id:
        raise ErroContratacao("Item não encontrado.", 404, "nao_encontrado")
    return item


# --- Documento ----------------------------------------------------------------------------------

def _validar_tipo_documento(tipo: str) -> None:
    if tipo not in ("etp", "tr"):
        raise ErroContratacao("O tipo do documento é ETP ou TR.")


def criar_documento(sessao: Session, tipo: str, nome: str, processo: str, link_sei: str | None, autor: Usuario) -> DocumentoContratacao:
    _validar_tipo_documento(tipo)
    nome = (nome or "").strip()
    if not nome:
        raise ErroContratacao("O nome é obrigatório.")
    documento = DocumentoContratacao(tipo=tipo, nome=nome[:300], processo=(processo or "").strip()[:100], link_sei=(link_sei or "").strip()[:500] or None,
                                     criador_id=autor.id, atualizado_por_id=autor.id)
    sessao.add(documento)
    sessao.flush()
    versoes.registrar(sessao, documento, "criacao", autor, "Documento criado")
    auditar(sessao, autor.login, "contratacao.criar", f"{tipo.upper()} {nome}", autor_id=autor.id, alvo_tipo="contratacao", alvo_id=documento.id)
    sessao.commit()
    return documento


def atualizar_documento(sessao: Session, documento: DocumentoContratacao, nome: str, processo: str, link_sei: str | None, autor: Usuario) -> DocumentoContratacao:
    nome = (nome or "").strip()
    if not nome:
        raise ErroContratacao("O nome é obrigatório.")
    versoes.antes_da_edicao(sessao, documento, autor)
    documento.nome, documento.processo, documento.link_sei = nome[:300], (processo or "").strip()[:100], (link_sei or "").strip()[:500] or None
    _tocar(documento, autor)
    auditar(sessao, autor.login, "contratacao.atualizar", documento.nome, autor_id=autor.id, alvo_tipo="contratacao", alvo_id=documento.id)
    sessao.commit()
    return documento


def alterar_situacao(sessao: Session, documento: DocumentoContratacao, situacao: str, autor: Usuario) -> DocumentoContratacao:
    if situacao not in ("rascunho", "em_revisao", "concluido"):
        raise ErroContratacao("Situação inválida.")
    if situacao == documento.situacao:
        return documento
    anterior = documento.situacao
    documento.situacao = situacao
    _tocar(documento, autor)
    versoes.registrar(sessao, documento, "situacao", autor, f"Situação: {anterior} → {situacao}")
    auditar(sessao, autor.login, "contratacao.situacao", f"{documento.nome}: {situacao}", autor_id=autor.id, alvo_tipo="contratacao", alvo_id=documento.id)
    sessao.commit()
    return documento


def excluir_documento(sessao: Session, documento: DocumentoContratacao, autor: Usuario) -> None:
    auditar(sessao, autor.login, "contratacao.excluir", documento.nome, autor_id=autor.id, alvo_tipo="contratacao", alvo_id=documento.id)
    sessao.delete(documento)
    sessao.commit()


def vincular_contrato(sessao: Session, documento: DocumentoContratacao, contrato_id: uuid.UUID | None, autor: Usuario) -> DocumentoContratacao:
    from app.models.contratos import Contrato

    if contrato_id is not None and sessao.get(Contrato, contrato_id) is None:
        raise ErroContratacao("Contrato não encontrado.", 404, "nao_encontrado")
    documento.contrato_id = contrato_id
    _tocar(documento, autor)
    auditar(sessao, autor.login, "contratacao.vincular", f"{documento.nome}: {contrato_id or 'sem vínculo'}", autor_id=autor.id, alvo_tipo="contratacao", alvo_id=documento.id)
    sessao.commit()
    return documento


def compartilhar(sessao: Session, documento: DocumentoContratacao, usuario_id: int, papel: str, autor: Usuario) -> MembroDocumento:
    if papel not in ("editor", "revisor"):
        raise ErroContratacao("O papel é editor ou revisor.")
    alvo = sessao.get(Usuario, usuario_id)
    if alvo is None or not alvo.ativo:
        raise ErroContratacao("Usuário não encontrado ou inativo.", 404, "nao_encontrado")
    if alvo.id == documento.criador_id:
        raise ErroContratacao("O criador já tem acesso total ao documento.")
    membro = next((m for m in documento.membros if m.usuario_id == usuario_id), None)
    if membro is None:
        membro = MembroDocumento(documento_id=documento.id, usuario_id=usuario_id, papel=papel)
        documento.membros.append(membro)
    else:
        membro.papel = papel
    auditar(sessao, autor.login, "contratacao.compartilhar", f"{documento.nome}: {alvo.login} ({papel})", autor_id=autor.id, alvo_tipo="contratacao", alvo_id=documento.id)
    sessao.commit()
    return membro


def remover_membro(sessao: Session, documento: DocumentoContratacao, usuario_id: int, autor: Usuario) -> None:
    membro = next((m for m in documento.membros if m.usuario_id == usuario_id), None)
    if membro is None:
        raise ErroContratacao("Essa pessoa não participa do documento.", 404, "nao_encontrado")
    documento.membros.remove(membro)
    auditar(sessao, autor.login, "contratacao.descompartilhar", f"{documento.nome}: usuário {usuario_id}", autor_id=autor.id, alvo_tipo="contratacao", alvo_id=documento.id)
    sessao.commit()


# --- Seções -------------------------------------------------------------------------------------

def _normalizar_secoes(documento: DocumentoContratacao) -> None:
    for n, secao in enumerate(sorted(documento.secoes, key=lambda s: (s.ordem, str(s.id))), start=1):
        secao.ordem = n


def criar_secao(sessao: Session, documento: DocumentoContratacao, titulo: str, autor: Usuario) -> SecaoContratacao:
    titulo = (titulo or "").strip()
    if not titulo:
        raise ErroContratacao("O título da seção é obrigatório.")
    versoes.antes_da_edicao(sessao, documento, autor)
    secao = SecaoContratacao(documento_id=documento.id, ordem=max((s.ordem for s in documento.secoes), default=0) + 1, titulo=titulo[:300])
    documento.secoes.append(secao)
    _tocar(documento, autor)
    sessao.commit()
    return secao


def atualizar_secao(sessao: Session, documento: DocumentoContratacao, secao_id: uuid.UUID, titulo: str, autor: Usuario) -> SecaoContratacao:
    secao = _carregar_secao(sessao, documento, secao_id)
    titulo = (titulo or "").strip()
    if not titulo:
        raise ErroContratacao("O título da seção é obrigatório.")
    versoes.antes_da_edicao(sessao, documento, autor)
    secao.titulo = titulo[:300]
    _tocar(documento, autor)
    sessao.commit()
    return secao


def excluir_secao(sessao: Session, documento: DocumentoContratacao, secao_id: uuid.UUID, autor: Usuario) -> None:
    secao = _carregar_secao(sessao, documento, secao_id)
    versoes.antes_da_edicao(sessao, documento, autor)
    for item in secao.itens:
        versoes.historico(sessao, documento, item.id, "removeu", item.conteudo_html or item.conteudo, None, autor, f"Seção «{secao.titulo}» excluída")
    documento.secoes.remove(secao)
    sessao.flush()
    _normalizar_secoes(documento)
    _tocar(documento, autor)
    sessao.commit()


def mover_secao(sessao: Session, documento: DocumentoContratacao, secao_id: uuid.UUID, ordem: int, autor: Usuario) -> None:
    secao = _carregar_secao(sessao, documento, secao_id)
    versoes.antes_da_edicao(sessao, documento, autor)
    outras = [s for s in sorted(documento.secoes, key=lambda s: s.ordem) if s.id != secao.id]
    posicao = max(0, min(len(outras), ordem - 1))
    outras.insert(posicao, secao)
    for n, s in enumerate(outras, start=1):
        s.ordem = n
    _tocar(documento, autor)
    sessao.commit()


# --- Itens --------------------------------------------------------------------------------------

def _irmaos(sessao: Session, secao_id: uuid.UUID, pai_id: uuid.UUID | None, exceto: uuid.UUID | None = None) -> list[ItemContratacao]:
    consulta = select(ItemContratacao).where(ItemContratacao.secao_id == secao_id, ItemContratacao.pai_id == pai_id if pai_id else ItemContratacao.pai_id.is_(None))
    lista = [i for i in sessao.scalars(consulta.order_by(ItemContratacao.ordem)) if i.id != exceto]
    return lista


def _renumerar(irmaos: list[ItemContratacao]) -> None:
    for n, i in enumerate(irmaos, start=1):
        i.ordem = n


def _profundidade(sessao: Session, item: ItemContratacao) -> int:
    n, atual = 0, item
    while atual.pai_id:
        atual, n = sessao.get(ItemContratacao, atual.pai_id), n + 1
    return n


def _validar_tipo(tipo: str) -> None:
    if tipo not in TIPOS_ITEM:
        raise ErroContratacao("Tipo de item inválido.")


def criar_item(sessao: Session, documento: DocumentoContratacao, secao_id: uuid.UUID, tipo: str, texto: str | None, html: str | None, pai_id: uuid.UUID | None,
               autor: Usuario, posicao: int | None = None, detalhe: str = "") -> ItemContratacao:
    secao = _carregar_secao(sessao, documento, secao_id)
    _validar_tipo(tipo)
    pai = None
    if pai_id is not None:
        pai = carregar_item(sessao, documento, pai_id)
        if pai.secao_id != secao.id:
            raise ErroContratacao("O item pai precisa estar na mesma seção.")
        if _profundidade(sessao, pai) + 1 >= MAXIMO_NIVEL:
            raise ErroContratacao(f"Profundidade máxima de {MAXIMO_NIVEL} níveis.")
    try:
        texto_ok, html_ok = conteudo.normalizar(texto, html)
    except conteudo.ErroConteudo as erro:
        raise ErroContratacao(str(erro)) from erro
    versoes.antes_da_edicao(sessao, documento, autor)
    irmaos = _irmaos(sessao, secao.id, pai.id if pai else None)
    item = ItemContratacao(secao_id=secao.id, pai_id=pai.id if pai else None, tipo=tipo, ordem=len(irmaos) + 1, conteudo=texto_ok, conteudo_html=html_ok)
    sessao.add(item)
    sessao.flush()
    if posicao is not None and 1 <= posicao <= len(irmaos):
        irmaos.insert(posicao - 1, item)
        _renumerar(irmaos)
    versoes.historico(sessao, documento, item.id, "criou", None, html_ok or texto_ok, autor, detalhe)
    _tocar(documento, autor)
    sessao.commit()
    return item


def atualizar_item(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, tipo: str | None, texto: str | None, html: str | None, autor: Usuario,
                   precisa_revisao: bool | None = None) -> ItemContratacao:
    item = carregar_item(sessao, documento, item_id)
    if tipo is not None:
        _validar_tipo(tipo)
    try:
        texto_ok, html_ok = conteudo.normalizar(texto, html)
    except conteudo.ErroConteudo as erro:
        raise ErroContratacao(str(erro)) from erro
    versoes.antes_da_edicao(sessao, documento, autor)
    antes = item.conteudo_html or item.conteudo
    if (html_ok or texto_ok) != antes:
        versoes.historico(sessao, documento, item.id, "editou", antes, html_ok or texto_ok, autor)
    item.conteudo, item.conteudo_html = texto_ok, html_ok
    if tipo is not None:
        item.tipo = tipo
    if precisa_revisao is not None:
        item.precisa_revisao = precisa_revisao
    _tocar(documento, autor)
    sessao.commit()
    return item


def _subarvore(item: ItemContratacao) -> list[ItemContratacao]:
    resultado = [item]
    for filho in item.filhos:
        resultado += _subarvore(filho)
    return resultado


def excluir_item(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, autor: Usuario) -> None:
    item = carregar_item(sessao, documento, item_id)
    versoes.antes_da_edicao(sessao, documento, autor)
    secao_id, pai_id = item.secao_id, item.pai_id
    for no in _subarvore(item):
        versoes.historico(sessao, documento, no.id, "removeu", no.conteudo_html or no.conteudo, None, autor, "Excluído com o item pai" if no.id != item.id else "")
    sessao.delete(item)
    sessao.flush()
    _renumerar(_irmaos(sessao, secao_id, pai_id))
    _tocar(documento, autor)
    sessao.commit()


def limpar_filhos(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, autor: Usuario) -> int:
    item = carregar_item(sessao, documento, item_id)
    versoes.antes_da_edicao(sessao, documento, autor)
    filhos = list(item.filhos)
    for filho in filhos:
        for no in _subarvore(filho):
            versoes.historico(sessao, documento, no.id, "removeu", no.conteudo_html or no.conteudo, None, autor, "Filhos limpos")
        sessao.delete(filho)
    _tocar(documento, autor)
    sessao.commit()
    return len(filhos)


def mover_item(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, secao_id: uuid.UUID, pai_id: uuid.UUID | None, ordem: int, autor: Usuario) -> ItemContratacao:
    item = carregar_item(sessao, documento, item_id)
    destino = _carregar_secao(sessao, documento, secao_id)
    novo_pai = carregar_item(sessao, documento, pai_id) if pai_id else None
    if novo_pai is not None:
        if novo_pai.secao_id != destino.id:
            raise ErroContratacao("O item pai precisa estar na seção de destino.")
        if novo_pai.id in {n.id for n in _subarvore(item)}:
            raise ErroContratacao("Um item não pode ser movido para dentro dele mesmo ou de um descendente.")
        if _profundidade(sessao, novo_pai) + 1 >= MAXIMO_NIVEL:
            raise ErroContratacao(f"Profundidade máxima de {MAXIMO_NIVEL} níveis.")
    versoes.antes_da_edicao(sessao, documento, autor)
    origem_secao, origem_pai = item.secao_id, item.pai_id
    item.pai_id = novo_pai.id if novo_pai else None
    for no in _subarvore(item):
        no.secao_id = destino.id
    sessao.flush()
    sessao.expire_all()
    item = carregar_item(sessao, documento, item_id)
    irmaos = _irmaos(sessao, destino.id, novo_pai.id if novo_pai else None, exceto=item.id)
    irmaos.insert(max(0, min(len(irmaos), ordem - 1)), item)
    _renumerar(irmaos)
    _renumerar(_irmaos(sessao, origem_secao, origem_pai, exceto=item.id))
    versoes.historico(sessao, documento, item.id, "moveu", None, None, autor, "Mudou de lugar")
    _tocar(documento, autor)
    sessao.commit()
    return item


def _copiar_no(sessao: Session, no: ItemContratacao, secao_id: uuid.UUID, pai_id: uuid.UUID | None, ordem: int) -> ItemContratacao:
    copia = ItemContratacao(secao_id=secao_id, pai_id=pai_id, tipo=no.tipo, ordem=ordem, conteudo=no.conteudo, conteudo_html=no.conteudo_html, precisa_revisao=no.precisa_revisao)
    sessao.add(copia)
    sessao.flush()
    for l in no.linhas_tabela:
        sessao.add(LinhaTabelaTr(item_id=copia.id, ordem=l.ordem, descricao=l.descricao, siafisico=l.siafisico, catser_catmat=l.catser_catmat, unidade=l.unidade,
                                 quantidade_mensal=l.quantidade_mensal, quantidade_objeto=l.quantidade_objeto))
    for n, filho in enumerate(no.filhos, start=1):
        _copiar_no(sessao, filho, secao_id, copia.id, n)
    return copia


def duplicar_item(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, autor: Usuario) -> ItemContratacao:
    """Copia o item com os descendentes, logo depois dele."""
    item = carregar_item(sessao, documento, item_id)
    versoes.antes_da_edicao(sessao, documento, autor)
    irmaos = _irmaos(sessao, item.secao_id, item.pai_id)
    copia = _copiar_no(sessao, item, item.secao_id, item.pai_id, len(irmaos) + 1)
    irmaos.insert(irmaos.index(item) + 1, copia)
    _renumerar(irmaos)
    for no in _subarvore(copia):
        versoes.historico(sessao, documento, no.id, "criou", None, no.conteudo_html or no.conteudo, autor, "Cópia de um item")
    _tocar(documento, autor)
    sessao.commit()
    return copia


def criar_em_lote(sessao: Session, documento: DocumentoContratacao, secao_id: uuid.UUID, pai_id: uuid.UUID | None, nos: list[conteudo.NoLote], autor: Usuario) -> int:
    """Grava a árvore da entrada em lote (já conferida na prévia) dentro da seção, sob `pai_id`."""
    secao = _carregar_secao(sessao, documento, secao_id)
    pai = carregar_item(sessao, documento, pai_id) if pai_id else None
    versoes.antes_da_edicao(sessao, documento, autor)
    total = 0

    def gravar(lista: list[conteudo.NoLote], pai_item: ItemContratacao | None) -> None:
        nonlocal total
        base = len(_irmaos(sessao, secao.id, pai_item.id if pai_item else None))
        for n, no in enumerate(lista, start=1):
            texto, html = conteudo.normalizar(no.conteudo, None)
            item = ItemContratacao(secao_id=secao.id, pai_id=pai_item.id if pai_item else None, tipo=no.tipo, ordem=base + n, conteudo=texto, conteudo_html=html, precisa_revisao=True)
            sessao.add(item)
            sessao.flush()
            versoes.historico(sessao, documento, item.id, "criou", None, html or texto, autor, "Entrada em lote")
            total += 1
            gravar(no.filhos, item)

    gravar(nos, pai)
    _tocar(documento, autor)
    sessao.commit()
    return total


# --- Duplicar documento -------------------------------------------------------------------------

def duplicar_documento(sessao: Session, documento: DocumentoContratacao, autor: Usuario) -> DocumentoContratacao:
    copia = DocumentoContratacao(tipo=documento.tipo, nome=f"Cópia de {documento.nome}"[:300], processo=documento.processo, link_sei=documento.link_sei, criador_id=autor.id, atualizado_por_id=autor.id)
    sessao.add(copia)
    sessao.flush()
    for secao in documento.secoes:
        nova = SecaoContratacao(documento_id=copia.id, ordem=secao.ordem, titulo=secao.titulo)
        sessao.add(nova)
        sessao.flush()
        for n, raiz in enumerate([i for i in secao.itens if i.pai_id is None], start=1):
            _copiar_no(sessao, raiz, nova.id, None, n)
    versoes.registrar(sessao, copia, "criacao", autor, f"Cópia de «{documento.nome}»")
    auditar(sessao, autor.login, "contratacao.duplicar", documento.nome, autor_id=autor.id, alvo_tipo="contratacao", alvo_id=copia.id)
    sessao.commit()
    return copia


# --- Tabela do TR -------------------------------------------------------------------------------

def _item_da_tabela(documento: DocumentoContratacao, item: ItemContratacao) -> bool:
    """A tabela estruturada pertence ao item 1.1 do TR (o primeiro item numérico da primeira seção)."""
    if documento.tipo != "tr":
        return False
    primeira = min(documento.secoes, key=lambda s: s.ordem, default=None)
    if primeira is None or item.secao_id != primeira.id or item.pai_id is not None:
        return False
    numericos = sorted([i for i in primeira.itens if i.pai_id is None and i.tipo in ("item", "subitem")], key=lambda i: i.ordem)
    return bool(numericos) and numericos[0].id == item.id


def adicionar_linha_tr(sessao: Session, documento: DocumentoContratacao, item_id: uuid.UUID, dados: dict, autor: Usuario) -> LinhaTabelaTr:
    item = carregar_item(sessao, documento, item_id)
    if not _item_da_tabela(documento, item):
        raise ErroContratacao("A tabela de itens só existe no item 1.1 do Termo de Referência.")
    descricao = (dados.get("descricao") or "").strip()
    if not descricao:
        raise ErroContratacao("Informe a descrição do item.")
    versoes.antes_da_edicao(sessao, documento, autor)
    linha = LinhaTabelaTr(item_id=item.id, ordem=len(item.linhas_tabela) + 1, descricao=descricao, siafisico=(dados.get("siafisico") or "").strip()[:60],
                          catser_catmat=(dados.get("catser_catmat") or "").strip()[:60], unidade=(dados.get("unidade") or "").strip()[:60],
                          quantidade_mensal=Decimal(dados.get("quantidade_mensal") or 0), quantidade_objeto=Decimal(dados.get("quantidade_objeto") or 0))
    item.linhas_tabela.append(linha)
    versoes.historico(sessao, documento, item.id, "editou", None, None, autor, f"Linha da tabela incluída: {descricao[:80]}")
    _tocar(documento, autor)
    sessao.commit()
    return linha


def excluir_linha_tr(sessao: Session, documento: DocumentoContratacao, linha_id: uuid.UUID, autor: Usuario) -> None:
    linha = sessao.get(LinhaTabelaTr, linha_id)
    if linha is None or linha.item.secao.documento_id != documento.id:
        raise ErroContratacao("Linha não encontrada.", 404, "nao_encontrado")
    versoes.antes_da_edicao(sessao, documento, autor)
    item = linha.item
    versoes.historico(sessao, documento, item.id, "editou", None, None, autor, f"Linha da tabela excluída: {linha.descricao[:80]}")
    item.linhas_tabela.remove(linha)
    sessao.flush()
    for n, l in enumerate(sorted(item.linhas_tabela, key=lambda x: x.ordem), start=1):
        l.ordem = n
    _tocar(documento, autor)
    sessao.commit()
