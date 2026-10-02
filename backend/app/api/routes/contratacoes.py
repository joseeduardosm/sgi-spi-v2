# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de Contratações (/api/contratacoes): ETP e TR, árvore de itens, revisões, versões e exportação.
"""Rotas `/api/contratacoes`.

Recurso ACL `contratacoes`: **LEITURA** vê os documentos em que é criador ou membro; **MODIFICACAO** também cria e importa; **CONTROLE_TOTAL**
(e SuperRoot) vê e administra todos. Dentro de cada documento valem os papéis: criador e **editores** editam e aplicam propostas;
**revisores** só comentam e propõem; só o criador (ou a administração) compartilha, exclui e vincula contrato. Documento sem acesso
responde 404 (não revela que existe).
"""

import hashlib
import uuid
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencias import exigir_acl
from app.api.respostas import CONFLITO, INVALIDO, VALIDACAO, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.contratacoes import DocumentoContratacao, ItemContratacao, SecaoContratacao
from app.models.contratos import Contrato
from app.models.usuario import Usuario
from app.schemas.usuarios import OpcaoUsuario
from app.services import servico_admin_usuarios
from app.schemas.contratacoes import (
    ConferenciaLeitura, CriacaoDocumento, CriacaoItem, DocumentoLeitura, DocumentoResumo, EdicaoItem, EntradaLote, GravacaoContratoVinculo,
    GravacaoDocumento, GravacaoLinhaTr, GravacaoMembro, GravacaoOrdem, GravacaoResolucao, GravacaoRestauroItem, GravacaoRevisao, GravacaoSecao,
    GravacaoSituacao, GravacaoVersao, ItemLeitura, LinhaTrLeitura, ListaDocumentos, MembroLeitura, MoverItem, PainelContratacoes, PreviaImportacao,
    PreviaLote, ResultadoLote, RevisaoLeitura, SecaoLeitura, VersaoDetalhe, VersaoResumo, ComentarioImportadoLeitura,
)
from app.services.contratacoes import acesso, arvore, conferencia, conteudo, docx_exportacao, docx_importacao, revisoes, versoes
from app.services.contratacoes.acesso import ErroContratacao

roteador = APIRouter(prefix="/contratacoes", tags=["Contratações"], responses=VALIDACAO)
ver = exigir_acl(acesso.RECURSO, NivelAcl.LEITURA)
criar = exigir_acl(acesso.RECURSO, NivelAcl.MODIFICACAO)
SEM_ACESSO = {status.HTTP_404_NOT_FOUND: {"description": "Documento inexistente ou sem acesso (`nao_encontrado`)."},
              status.HTTP_403_FORBIDDEN: {"description": "Papel insuficiente no documento (`sem_permissao`) ou sem ACL (`acl_negado`)."}}
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@contextmanager
def _traduzir(sessao: Session | None = None):
    """Erros do serviço viram a resposta padrão `{"detalhe", "codigo"}`."""
    try:
        yield
    except ErroContratacao as erro:
        if sessao is not None:
            sessao.rollback()
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _carregar(sessao: Session, usuario: Usuario, documento_id: uuid.UUID, minimo: str = "ver") -> tuple[DocumentoContratacao, str]:
    with _traduzir():
        return acesso.obter(sessao, usuario, documento_id, minimo)


def _nomes(sessao: Session, ids: set[int | None]) -> dict[int, Usuario]:
    ids = {i for i in ids if i is not None}
    return {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids)))} if ids else {}


def _numeros_contrato(sessao: Session, ids: set) -> dict:
    ids = {i for i in ids if i is not None}
    return {c.id: c.numero for c in sessao.scalars(select(Contrato).where(Contrato.id.in_(ids)))} if ids else {}


def _resumo(sessao: Session, d: DocumentoContratacao, papel: str, nomes: dict, contratos: dict) -> DocumentoResumo:
    criador = nomes.get(d.criador_id)
    return DocumentoResumo(
        id=d.id, tipo=d.tipo, nome=d.nome, processo=d.processo, link_sei=d.link_sei, situacao=d.situacao, criador_id=d.criador_id,
        criador_nome=(criador.nome_completo or criador.login) if criador else "—", contrato_id=d.contrato_id, contrato_numero=contratos.get(d.contrato_id),
        criado_em=d.criado_em, atualizado_em=d.atualizado_em, meu_papel=papel, revisoes_abertas=len(revisoes.abertas(d)))


def _carregar_documentos(sessao: Session, consulta) -> list[DocumentoContratacao]:
    return list(sessao.scalars(consulta.options(selectinload(DocumentoContratacao.secoes).selectinload(SecaoContratacao.itens).selectinload(ItemContratacao.revisoes),
                                                selectinload(DocumentoContratacao.membros)).order_by(DocumentoContratacao.atualizado_em.desc())).unique())


def _resumos(sessao: Session, usuario: Usuario, docs: list[DocumentoContratacao]) -> list[DocumentoResumo]:
    nomes = _nomes(sessao, {d.criador_id for d in docs})
    contratos = _numeros_contrato(sessao, {d.contrato_id for d in docs})
    return [_resumo(sessao, d, acesso.papel(sessao, usuario, d) or "revisor", nomes, contratos) for d in docs]


def _leitura(sessao: Session, d: DocumentoContratacao, papel: str) -> DocumentoLeitura:
    nomes = _nomes(sessao, {d.criador_id, *(m.usuario_id for m in d.membros)})
    contratos = _numeros_contrato(sessao, {d.contrato_id})
    base = _resumo(sessao, d, papel, nomes, contratos)
    secoes = []
    for secao in sorted(d.secoes, key=lambda s: s.ordem):
        marcas = conteudo.marcadores(secao.ordem, secao.itens)
        itens = []
        for i in docx_exportacao.itens_em_ordem(secao):
            itens.append(ItemLeitura(
                id=i.id, secao_id=i.secao_id, pai_id=i.pai_id, tipo=i.tipo, ordem=i.ordem, marcador=marcas.get(i.id, ""), conteudo=i.conteudo,
                conteudo_html=i.conteudo_html, precisa_revisao=i.precisa_revisao,
                revisoes=[RevisaoLeitura.model_validate(r, from_attributes=True) for r in i.revisoes],
                comentarios_importados=[ComentarioImportadoLeitura.model_validate(c, from_attributes=True) for c in i.comentarios_importados],
                linhas_tabela=[LinhaTrLeitura.model_validate(l, from_attributes=True) for l in i.linhas_tabela],
                tem_tabela_tr=arvore._item_da_tabela(d, i)))
        secoes.append(SecaoLeitura(id=secao.id, ordem=secao.ordem, titulo=secao.titulo, itens=itens))
    membros = [MembroLeitura(usuario_id=m.usuario_id, nome=(nomes[m.usuario_id].nome_completo or nomes[m.usuario_id].login) if m.usuario_id in nomes else "—",
                             login=nomes[m.usuario_id].login if m.usuario_id in nomes else "", papel=m.papel) for m in d.membros]
    return DocumentoLeitura(**base.model_dump(), pode_editar=acesso.pode_editar(papel), pode_gerir=papel in ("administrador", "criador"), pode_revisar=True,
                            secoes=secoes, membros=membros)


@roteador.get("/opcoes-usuarios", response_model=list[OpcaoUsuario], summary="Usuários para compartilhar o documento",
              description="Usuários ativos por nome, login ou cargo (`busca`, até 20). Exige MODIFICACAO em `contratacoes` (quem cria documentos compartilha).")
def opcoes_usuarios(busca: str | None = Query(None, max_length=100), sessao: Session = Depends(obter_sessao), _: Usuario = Depends(criar)) -> list[OpcaoUsuario]:
    return servico_admin_usuarios.opcoes(sessao, busca, 20)


# --- Painel e listagem --------------------------------------------------------------------------

@roteador.get("/painel", response_model=PainelContratacoes, summary="Andamento dos documentos",
              description="Totais por situação e tipo dos documentos que o usuário enxerga, revisões abertas e concluídos sem vínculo com contrato.")
def painel(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> PainelContratacoes:
    return PainelContratacoes(**conferencia.painel(sessao, acesso.visiveis(sessao, usuario)))


@roteador.get("/documentos", response_model=ListaDocumentos, summary="Listar ETP e TR",
              description="Os documentos que o usuário enxerga (criador, membro ou administração), do mais recente ao mais antigo.")
def listar(tipo: str | None = Query(None, pattern="^(etp|tr)$"), situacao: str | None = Query(None, pattern="^(rascunho|em_revisao|concluido)$"),
           busca: str | None = Query(None, max_length=200, description="Nome ou processo."), contrato_id: uuid.UUID | None = None,
           sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> ListaDocumentos:
    consulta = acesso.visiveis(sessao, usuario)
    if tipo:
        consulta = consulta.where(DocumentoContratacao.tipo == tipo)
    if situacao:
        consulta = consulta.where(DocumentoContratacao.situacao == situacao)
    if contrato_id:
        consulta = consulta.where(DocumentoContratacao.contrato_id == contrato_id)
    if busca and busca.strip():
        termo = f"%{busca.strip().lower()}%"
        from sqlalchemy import func, or_
        consulta = consulta.where(or_(func.lower(DocumentoContratacao.nome).like(termo), func.lower(DocumentoContratacao.processo).like(termo)))
    from app.services import servico_acl

    nivel = servico_acl.resolver_acesso(sessao, usuario, acesso.RECURSO)
    pode = usuario.superusuario or NivelAcl.posicao(nivel) >= NivelAcl.posicao(NivelAcl.MODIFICACAO)
    return ListaDocumentos(pode_criar=pode, itens=_resumos(sessao, usuario, _carregar_documentos(sessao, consulta)))


@roteador.get("/por-contrato/{contrato_id}", response_model=list[DocumentoResumo], summary="Documentos de um contrato",
              description="ETP e TR vinculados ao contrato que o usuário enxerga (aba da ficha do contrato).")
def por_contrato(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[DocumentoResumo]:
    consulta = acesso.visiveis(sessao, usuario).where(DocumentoContratacao.contrato_id == contrato_id)
    return _resumos(sessao, usuario, _carregar_documentos(sessao, consulta))


# --- Documento ----------------------------------------------------------------------------------

@roteador.post("/documentos", response_model=DocumentoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar ETP ou TR",
               description="Exige MODIFICACAO. O autor vira o criador; já nasce a versão 1.", responses=INVALIDO)
def criar_documento(dados: CriacaoDocumento, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(criar)) -> DocumentoLeitura:
    with _traduzir(sessao):
        d = arvore.criar_documento(sessao, dados.tipo, dados.nome, dados.processo, dados.link_sei, usuario)
    return _leitura(sessao, d, "criador")


@roteador.get("/documentos/{documento_id}", response_model=DocumentoLeitura, summary="Abrir documento",
              description="O documento com seções e itens em lista plana (hierarquia por `pai_id`), revisões, tabela do TR e membros.", responses=SEM_ACESSO)
def abrir(documento_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id)
    return _leitura(sessao, d, papel)


@roteador.put("/documentos/{documento_id}", response_model=DocumentoLeitura, summary="Alterar nome, processo e link", responses={**SEM_ACESSO, **INVALIDO})
def alterar(documento_id: uuid.UUID, dados: GravacaoDocumento, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.atualizar_documento(sessao, d, dados.nome, dados.processo, dados.link_sei, usuario)
    return _leitura(sessao, d, papel)


@roteador.delete("/documentos/{documento_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir documento",
                 description="Só o criador ou a administração. Apaga também versões e histórico.", responses=SEM_ACESSO)
def excluir(documento_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> Response:
    d, _ = _carregar(sessao, usuario, documento_id, "gerir")
    arvore.excluir_documento(sessao, d, usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.put("/documentos/{documento_id}/situacao", response_model=DocumentoLeitura, summary="Mudar a situação",
              description="`rascunho`, `em_revisao` ou `concluido`. Gera uma versão. Para **concluir** roda a conferência: os bloqueios (proposta não aplicada) impedem; "
              "os alertas exigem `confirmar = true` (`409`, `codigo = conferencia`).", responses={**SEM_ACESSO, **CONFLITO, **INVALIDO})
def mudar_situacao(documento_id: uuid.UUID, dados: GravacaoSituacao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    if dados.situacao == "concluido" and d.situacao != "concluido":
        c = conferencia.conferir(d)
        if c["bloqueios"]:
            raise ErroApi(status.HTTP_409_CONFLICT, "Há pendências que impedem concluir: " + " ".join(c["bloqueios"]), "conferencia")
        if c["alertas"] and not dados.confirmar:
            raise ErroApi(status.HTTP_409_CONFLICT, "Há alertas na conferência; confirme para concluir mesmo assim: " + " ".join(c["alertas"]), "conferencia")
    with _traduzir(sessao):
        arvore.alterar_situacao(sessao, d, dados.situacao, usuario)
    return _leitura(sessao, d, papel)


@roteador.get("/documentos/{documento_id}/conferencia", response_model=ConferenciaLeitura, summary="Conferência antes de concluir",
              description="Seções vazias, itens a revisar, propostas e comentários abertos, processo SEI vazio.", responses=SEM_ACESSO)
def conferir(documento_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> ConferenciaLeitura:
    d, _ = _carregar(sessao, usuario, documento_id)
    return ConferenciaLeitura(**conferencia.conferir(d))


@roteador.post("/documentos/{documento_id}/duplicar", response_model=DocumentoLeitura, status_code=status.HTTP_201_CREATED, summary="Duplicar documento",
               description="Cópia em rascunho, do usuário, sem revisões, membros nem vínculo. Exige MODIFICACAO.", responses=SEM_ACESSO)
def duplicar(documento_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(criar)) -> DocumentoLeitura:
    d, _ = _carregar(sessao, usuario, documento_id)
    copia = arvore.duplicar_documento(sessao, d, usuario)
    return _leitura(sessao, copia, "criador")


@roteador.put("/documentos/{documento_id}/contrato", response_model=DocumentoLeitura, summary="Vincular a um contrato",
              description="`contrato_id = null` desfaz. Só o criador ou a administração.", responses={**SEM_ACESSO, **resposta_nao_encontrado("Contrato")})
def vincular(documento_id: uuid.UUID, dados: GravacaoContratoVinculo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "gerir")
    with _traduzir(sessao):
        arvore.vincular_contrato(sessao, d, dados.contrato_id, usuario)
    return _leitura(sessao, d, papel)


@roteador.put("/documentos/{documento_id}/membros/{usuario_id}", response_model=list[MembroLeitura], summary="Compartilhar o documento",
              description="Inclui ou muda o papel (`editor` edita; `revisor` comenta e propõe). Só o criador ou a administração.", responses={**SEM_ACESSO, **INVALIDO})
def compartilhar(documento_id: uuid.UUID, usuario_id: int, dados: GravacaoMembro, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[MembroLeitura]:
    d, papel = _carregar(sessao, usuario, documento_id, "gerir")
    with _traduzir(sessao):
        arvore.compartilhar(sessao, d, usuario_id, dados.papel, usuario)
    return _leitura(sessao, d, papel).membros


@roteador.delete("/documentos/{documento_id}/membros/{usuario_id}", response_model=list[MembroLeitura], summary="Deixar de compartilhar", responses=SEM_ACESSO)
def descompartilhar(documento_id: uuid.UUID, usuario_id: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[MembroLeitura]:
    d, papel = _carregar(sessao, usuario, documento_id, "gerir")
    with _traduzir(sessao):
        arvore.remover_membro(sessao, d, usuario_id, usuario)
    return _leitura(sessao, d, papel).membros


# --- Seções -------------------------------------------------------------------------------------

@roteador.post("/documentos/{documento_id}/secoes", response_model=DocumentoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar seção", responses={**SEM_ACESSO, **INVALIDO})
def criar_secao(documento_id: uuid.UUID, dados: GravacaoSecao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.criar_secao(sessao, d, dados.titulo, usuario)
    return _leitura(sessao, d, papel)


@roteador.put("/documentos/{documento_id}/secoes/{secao_id}", response_model=DocumentoLeitura, summary="Renomear seção", responses={**SEM_ACESSO, **INVALIDO})
def renomear_secao(documento_id: uuid.UUID, secao_id: uuid.UUID, dados: GravacaoSecao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.atualizar_secao(sessao, d, secao_id, dados.titulo, usuario)
    return _leitura(sessao, d, papel)


@roteador.delete("/documentos/{documento_id}/secoes/{secao_id}", response_model=DocumentoLeitura, summary="Excluir seção (com os itens)", responses={**SEM_ACESSO, **INVALIDO})
def excluir_secao(documento_id: uuid.UUID, secao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.excluir_secao(sessao, d, secao_id, usuario)
    return _leitura(sessao, d, papel)


@roteador.put("/documentos/{documento_id}/secoes/{secao_id}/ordem", response_model=DocumentoLeitura, summary="Mover seção", responses={**SEM_ACESSO, **INVALIDO})
def mover_secao(documento_id: uuid.UUID, secao_id: uuid.UUID, dados: GravacaoOrdem, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.mover_secao(sessao, d, secao_id, dados.ordem, usuario)
    return _leitura(sessao, d, papel)


# --- Itens --------------------------------------------------------------------------------------

@roteador.post("/documentos/{documento_id}/itens", response_model=DocumentoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar item",
               description="Item, subitem, inciso, alínea ou subseção, na seção e sob o pai indicados (até 8 níveis). O HTML é sanitizado.", responses={**SEM_ACESSO, **INVALIDO})
def criar_item(documento_id: uuid.UUID, dados: CriacaoItem, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.criar_item(sessao, d, dados.secao_id, dados.tipo, dados.conteudo, dados.conteudo_html, dados.pai_id, usuario, dados.posicao)
    return _leitura(sessao, d, papel)


@roteador.put("/documentos/{documento_id}/itens/{item_id}", response_model=DocumentoLeitura, summary="Editar item",
              description="Grava o conteúdo (HTML sanitizado) e registra o antes e o depois no histórico do item.", responses={**SEM_ACESSO, **INVALIDO})
def editar_item(documento_id: uuid.UUID, item_id: uuid.UUID, dados: EdicaoItem, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.atualizar_item(sessao, d, item_id, dados.tipo, dados.conteudo, dados.conteudo_html, usuario, dados.precisa_revisao)
    return _leitura(sessao, d, papel)


@roteador.delete("/documentos/{documento_id}/itens/{item_id}", response_model=DocumentoLeitura, summary="Excluir item (com os filhos)", responses={**SEM_ACESSO, **INVALIDO})
def excluir_item(documento_id: uuid.UUID, item_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.excluir_item(sessao, d, item_id, usuario)
    return _leitura(sessao, d, papel)


@roteador.post("/documentos/{documento_id}/itens/{item_id}/mover", response_model=DocumentoLeitura, summary="Mover item (com a subárvore)", responses={**SEM_ACESSO, **INVALIDO})
def mover_item(documento_id: uuid.UUID, item_id: uuid.UUID, dados: MoverItem, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.mover_item(sessao, d, item_id, dados.secao_id, dados.pai_id, dados.ordem, usuario)
    return _leitura(sessao, d, papel)


@roteador.post("/documentos/{documento_id}/itens/{item_id}/duplicar", response_model=DocumentoLeitura, status_code=status.HTTP_201_CREATED, summary="Duplicar item (com a subárvore)",
               responses={**SEM_ACESSO, **INVALIDO})
def duplicar_item(documento_id: uuid.UUID, item_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.duplicar_item(sessao, d, item_id, usuario)
    return _leitura(sessao, d, papel)


@roteador.post("/documentos/{documento_id}/itens/{item_id}/limpar-filhos", response_model=DocumentoLeitura, summary="Apagar só os filhos do item", responses={**SEM_ACESSO, **INVALIDO})
def limpar_filhos(documento_id: uuid.UUID, item_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.limpar_filhos(sessao, d, item_id, usuario)
    return _leitura(sessao, d, papel)


@roteador.post("/documentos/{documento_id}/lote/previa", response_model=PreviaLote, summary="Prévia da entrada em lote",
               description="Interpreta o texto (`#`, `@`, `**`, `$$`) e devolve a árvore que seria criada, sem gravar.", responses={**SEM_ACESSO, **INVALIDO})
def previa_lote(documento_id: uuid.UUID, dados: EntradaLote, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> PreviaLote:
    _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir():
        try:
            return PreviaLote(itens=conteudo.achatar_lote(conteudo.interpretar_lote(dados.texto)))
        except conteudo.ErroConteudo as erro:
            raise ErroContratacao(str(erro)) from erro


@roteador.post("/documentos/{documento_id}/lote", response_model=ResultadoLote, status_code=status.HTTP_201_CREATED, summary="Criar itens em lote",
               description="Grava a árvore da entrada em lote; os itens nascem marcados como \"precisa de revisão\".", responses={**SEM_ACESSO, **INVALIDO})
def criar_lote(documento_id: uuid.UUID, dados: EntradaLote, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> ResultadoLote:
    d, _ = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        try:
            nos = conteudo.interpretar_lote(dados.texto)
        except conteudo.ErroConteudo as erro:
            raise ErroContratacao(str(erro)) from erro
        if not nos:
            raise ErroContratacao("Nenhum item reconhecido no texto.")
        return ResultadoLote(criados=arvore.criar_em_lote(sessao, d, dados.secao_id, dados.pai_id, nos, usuario))


@roteador.post("/documentos/{documento_id}/itens/{item_id}/linhas-tr", response_model=DocumentoLeitura, status_code=status.HTTP_201_CREATED, summary="Incluir linha na tabela do TR",
               description="Só no item 1.1 do TR.", responses={**SEM_ACESSO, **INVALIDO})
def incluir_linha(documento_id: uuid.UUID, item_id: uuid.UUID, dados: GravacaoLinhaTr, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.adicionar_linha_tr(sessao, d, item_id, dados.model_dump(), usuario)
    return _leitura(sessao, d, papel)


@roteador.delete("/documentos/{documento_id}/linhas-tr/{linha_id}", response_model=DocumentoLeitura, summary="Excluir linha da tabela do TR", responses={**SEM_ACESSO, **INVALIDO})
def excluir_linha(documento_id: uuid.UUID, linha_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        arvore.excluir_linha_tr(sessao, d, linha_id, usuario)
    return _leitura(sessao, d, papel)


# --- Revisões -----------------------------------------------------------------------------------

@roteador.post("/documentos/{documento_id}/itens/{item_id}/revisoes", response_model=DocumentoLeitura, status_code=status.HTTP_201_CREATED, summary="Comentar ou propor alteração",
               description="Qualquer papel (inclusive revisor). Com `conteudo_proposto*` é uma proposta; sem, um comentário. O criador e os editores são avisados.", responses={**SEM_ACESSO, **INVALIDO})
def criar_revisao(documento_id: uuid.UUID, item_id: uuid.UUID, dados: GravacaoRevisao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "revisar")
    with _traduzir(sessao):
        revisoes.criar(sessao, d, item_id, dados.comentario, dados.conteudo_proposto, dados.conteudo_proposto_html, usuario)
    return _leitura(sessao, d, papel)


@roteador.post("/documentos/{documento_id}/itens/{item_id}/revisoes/{revisao_id}/aplicar", response_model=DocumentoLeitura, summary="Aplicar proposta",
               description="Só o criador, os editores e a administração. Copia a proposta para o item e gera uma versão.", responses={**SEM_ACESSO, **INVALIDO})
def aplicar_revisao(documento_id: uuid.UUID, item_id: uuid.UUID, revisao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        revisoes.aplicar(sessao, d, item_id, revisao_id, usuario)
    return _leitura(sessao, d, papel)


@roteador.post("/documentos/{documento_id}/itens/{item_id}/revisoes/{revisao_id}/resolver", response_model=DocumentoLeitura, summary="Marcar revisão como resolvida (ou reabrir)",
               responses={**SEM_ACESSO, **INVALIDO})
def resolver_revisao(documento_id: uuid.UUID, item_id: uuid.UUID, revisao_id: uuid.UUID, dados: GravacaoResolucao, sessao: Session = Depends(obter_sessao),
                     usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        revisoes.resolver(sessao, d, item_id, revisao_id, dados.resolvida, usuario)
    return _leitura(sessao, d, papel)


# --- Versões e histórico ------------------------------------------------------------------------

def _versao(v) -> VersaoResumo:
    return VersaoResumo(numero=v.numero, tipo=v.tipo, tipo_rotulo=versoes.ROTULOS_TIPO.get(v.tipo, v.tipo), resumo=v.resumo, autor_nome=v.autor_nome, criada_em=v.criada_em)


@roteador.get("/documentos/{documento_id}/versoes", response_model=list[VersaoResumo], summary="Versões do documento",
              description="Da mais recente para a mais antiga: criação, importação, mudanças de situação, propostas aplicadas, versões salvas e o estado antes de cada sessão de edição.", responses=SEM_ACESSO)
def listar_versoes(documento_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[VersaoResumo]:
    d, _ = _carregar(sessao, usuario, documento_id)
    return [_versao(v) for v in versoes.listar(sessao, d)]


@roteador.post("/documentos/{documento_id}/versoes", response_model=VersaoResumo, status_code=status.HTTP_201_CREATED, summary="Salvar uma versão",
               description="Grava a foto atual com um resumo das alterações.", responses=SEM_ACESSO)
def salvar_versao(documento_id: uuid.UUID, dados: GravacaoVersao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> VersaoResumo:
    d, _ = _carregar(sessao, usuario, documento_id, "editar")
    versao = versoes.registrar(sessao, d, "manual", usuario, dados.resumo)
    sessao.commit()
    return _versao(versao)


@roteador.get("/documentos/{documento_id}/versoes/{numero}", response_model=VersaoDetalhe, summary="Visualizar uma versão", description="A foto completa do documento naquela versão.",
              responses={**SEM_ACESSO, **resposta_nao_encontrado("Versão")})
def ver_versao(documento_id: uuid.UUID, numero: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> VersaoDetalhe:
    d, _ = _carregar(sessao, usuario, documento_id)
    with _traduzir():
        v = versoes.obter(sessao, d, numero)
    return VersaoDetalhe(**_versao(v).model_dump(), foto=v.foto)


@roteador.get("/documentos/{documento_id}/versoes/{numero}/alteracoes", response_model=dict[str, Any], summary="O que mudou nesta versão",
              description="Compara com a versão anterior (ou com `contra`): itens **incluídos**, **removidos**, **alterados** (diferença por palavra com `<ins>`/`<del>`) e **movidos**, e mudanças de nome, processo e situação.",
              responses={**SEM_ACESSO, **resposta_nao_encontrado("Versão")})
def alteracoes(documento_id: uuid.UUID, numero: int, contra: int | None = Query(None, ge=1, description="Número da versão base da comparação."),
               sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> dict[str, Any]:
    d, _ = _carregar(sessao, usuario, documento_id)
    with _traduzir():
        return versoes.alteracoes(sessao, d, numero, contra)


@roteador.post("/documentos/{documento_id}/versoes/{numero}/restaurar", response_model=DocumentoLeitura, summary="Restaurar uma versão",
               description="Recria a árvore como estava na versão (guardando antes o estado atual) e gera uma nova versão \"Restaurou a versão N\".", responses={**SEM_ACESSO, **resposta_nao_encontrado("Versão")})
def restaurar_versao(documento_id: uuid.UUID, numero: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        versoes.restaurar_versao(sessao, d, numero, usuario)
        sessao.commit()
    sessao.expire_all()
    return _leitura(sessao, d, papel)


@roteador.get("/documentos/{documento_id}/itens/{item_id}/historico", response_model=list[dict[str, Any]], summary="Histórico do item",
              description="Cada edição do item (mais recente primeiro) com o HTML antes e depois e a diferença por palavra. Sobrevive à exclusão do item.", responses=SEM_ACESSO)
def historico_item(documento_id: uuid.UUID, item_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[dict[str, Any]]:
    d, _ = _carregar(sessao, usuario, documento_id)
    return [{**h, "id": str(h["id"])} for h in versoes.historico_do_item(sessao, d, item_id)]


@roteador.post("/documentos/{documento_id}/historico/{historico_id}/restaurar", response_model=DocumentoLeitura, summary="Restaurar só um item",
               description="Volta o conteúdo do item ao estado `antes` ou `depois` de uma edição do histórico (`409` se o item não existe mais).", responses={**SEM_ACESSO, **CONFLITO})
def restaurar_item(documento_id: uuid.UUID, historico_id: uuid.UUID, dados: GravacaoRestauroItem, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> DocumentoLeitura:
    d, papel = _carregar(sessao, usuario, documento_id, "editar")
    with _traduzir(sessao):
        versoes.restaurar_item(sessao, d, historico_id, dados.estado, usuario)
        sessao.commit()
    return _leitura(sessao, d, papel)


# --- Exportar e importar ------------------------------------------------------------------------

def _nome_arquivo(d: DocumentoContratacao, extensao: str) -> str:
    base = "".join(c if c.isalnum() or c in " -_" else "_" for c in f"{d.tipo.upper()} {d.nome}").strip()[:80] or d.tipo.upper()
    return f"{base}.{extensao}"


@roteador.get("/documentos/{documento_id}/exportar/word", summary="Exportar em Word (.docx)",
              description="Gera o .docx sobre o modelo original do ETP ou TR (Verdana 10, marcadores jurídicos em negrito, tabela do TR depois do item 1.1).",
              responses={**SEM_ACESSO, 200: {"content": {DOCX: {}}, "description": "Arquivo .docx."}})
def exportar_word(documento_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> Response:
    d, _ = _carregar(sessao, usuario, documento_id)
    dados = docx_exportacao.gerar_word(d)
    return Response(dados, media_type=DOCX, headers={"Content-Disposition": f'attachment; filename="{_nome_arquivo(d, "docx")}"'})


@roteador.get("/documentos/{documento_id}/exportar/pdf", summary="Exportar em PDF",
              description="Gera o PDF do documento com o mesmo conteúdo do Word.", responses={**SEM_ACESSO, 200: {"content": {"application/pdf": {}}, "description": "Arquivo PDF."}})
def exportar_pdf(documento_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> Response:
    d, _ = _carregar(sessao, usuario, documento_id)
    dados = docx_exportacao.gerar_pdf(d, autor=usuario.nome_completo or usuario.login)
    return Response(dados, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{_nome_arquivo(d, "pdf")}"'})


@roteador.post("/importar-word", response_model=PreviaImportacao, summary="Importar Word (prévia e confirmação)",
               description="Envie o .docx (até 10 MB). Com `confirmar = false` devolve só a **prévia** (seções, itens, avisos, itens a revisar, comentários do Word). "
               "Com `confirmar = true` cria o documento (rascunho, do usuário) e devolve também `documento_id`. Exige MODIFICACAO. Erros: `400` (`docx_invalido`, `docx_vazio`), `413` (`arquivo_grande`).",
               responses=INVALIDO)
async def importar_word(arquivo: UploadFile = File(...), tipo: str = Form(..., pattern="^(etp|tr)$"), nome: str = Form("", max_length=300), processo: str = Form("", max_length=100),
                        confirmar: bool = Form(False), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(criar)) -> PreviaImportacao:
    dados = await arquivo.read(docx_importacao.LIMITE_ARQUIVO + 1)
    with _traduzir(sessao):
        previa = docx_importacao.ler(dados, arquivo.filename or "documento.docx")
        documento_id = None
        if confirmar:
            titulo = nome.strip() or previa["nome_sugerido"][:300] or (arquivo.filename or "Documento importado").rsplit(".", 1)[0][:300]
            documento_id = docx_importacao.gravar(sessao, previa, tipo, titulo, processo.strip() or previa["processo_sugerido"], None, usuario).id
    return PreviaImportacao(**previa, documento_id=documento_id)
