# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do Módulo Notícias (portal público e gestão editorial).
"""Rotas `/api/portal` e `/api/noticias`.

- **Públicas (sem token):** página inicial do portal, arquivo de notícias, detalhe e arquivos das notícias publicadas.
- **Gestão (login + ACL `noticias`):** notícias, fluxo de aprovação, capa, anexos, categorias, atalhos e configuração.
"""

import json
import uuid
from contextlib import contextmanager
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, VALIDACAO, resposta_nao_encontrado
from app.core.banco import agora_utc, obter_sessao
from app.core.erros import ErroApi
from app.models.anexo import Anexo
from app.models.noticias import AtalhoPortal, CategoriaNoticia, Noticia, RevisaoNoticia
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.schemas.noticias import (
    Aprovacao, ArquivoLeitura, AtalhoLeitura, CategoriaLeitura, CienciaLeitura, CienciaResumo, ConfiguracaoGestao, ConfiguracaoLeitura,
    Devolucao, GravacaoCategoria, GravacaoConfiguracao, GravacaoNoticia, NoticiaCartao, NoticiaGestao, NoticiaGestaoResumo, NoticiaPublica,
    PaginaNoticias, PapelNoticias, Pessoa, PessoaCiencia, PortalLeitura, Reordenacao, RevisaoLeitura, SetorResumo,
)
from app.services import servico_anexos
from app.services.noticias import servico_noticias as servico
from app.services.noticias.servico_noticias import DadosNoticia, ErroNoticia

roteador = APIRouter(tags=["Notícias e portal"], responses=VALIDACAO)
SEM_PERMISSAO = {status.HTTP_403_FORBIDDEN: {"description": "Sem o nível exigido em `noticias` (`sem_permissao`)."}}
NAO_ENCONTRADA = resposta_nao_encontrado("Notícia")
# Cache dos arquivos públicos (as versões da capa não mudam: um novo recorte gera arquivos novos)
CACHE_PUBLICO = "public, max-age=86400"


@contextmanager
def _traduzir():
    try:
        yield
    except ErroNoticia as erro:
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _utc(valor: datetime | None) -> datetime | None:
    return servico._comparavel(valor)


def _categoria(c: CategoriaNoticia | None) -> CategoriaLeitura | None:
    return CategoriaLeitura.model_validate(c, from_attributes=True) if c else None


def _capa_publica(n: Noticia) -> dict[str, str]:
    return {t: f"/api/noticias/publicas/{n.slug}/arquivos/{a}" for t, a in (n.capa_versoes or {}).items()}


def _capa_gestao(n: Noticia) -> dict[str, str]:
    return {t: f"/api/noticias/{n.id}/arquivos/{a}" for t, a in (n.capa_versoes or {}).items()}


def _cartao(n: Noticia) -> NoticiaCartao:
    return NoticiaCartao(id=n.id, slug=n.slug, titulo=n.titulo, linha_fina=n.linha_fina, categoria=_categoria(n.categoria),
                         publicada_em=_utc(n.publicar_em), fixada=n.fixada, capa=_capa_publica(n), capa_alt=n.capa_alt, capa_modo=n.capa_modo)


def _arquivos(n: Noticia, base: str) -> list[ArquivoLeitura]:
    return [ArquivoLeitura(id=a.anexo.id, nome=a.anexo.nome_original, tamanho=a.anexo.tamanho, tipo=a.anexo.tipo_conteudo,
                           url=f"{base}/arquivos/{a.anexo.id}") for a in n.anexos if a.anexo.excluido_em is None]


def _atalho(a: AtalhoPortal) -> AtalhoLeitura:
    return AtalhoLeitura(id=a.id, titulo=a.titulo, url=a.url, nova_aba=a.nova_aba, ativo=a.ativo, ordem=a.ordem,
                         imagem=f"/api/portal/atalhos/{a.id}/imagem" if a.imagem_exibicao_id else None)


def _inline(anexo: Anexo, cache: str | None = None) -> FileResponse:
    """Arquivo exibido no navegador (imagem ou PDF), com o nome original para quem baixar."""
    arquivo = servico_anexos.caminho(anexo)
    if anexo.excluido_em is not None or not arquivo.is_file():
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado.", "nao_encontrado")
    resposta = FileResponse(arquivo, media_type=anexo.tipo_conteudo, filename=servico_anexos.nome_seguro(anexo.nome_original),
                            content_disposition_type="inline")
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    if cache:
        resposta.headers["Cache-Control"] = cache
    return resposta


# ---------------------------------------------------------------------------------------------
# Portal público (sem token)
# ---------------------------------------------------------------------------------------------

@roteador.get("/portal", response_model=PortalLeitura, summary="Página inicial do portal (pública)",
              description="Sem login. Slider conforme a configuração (automático: fixadas e mais recentes; curadoria: ordem manual), "
                          "cartões sem repetir os slides, atalhos ativos e categorias ativas.")
def pagina_inicial(sessao: Session = Depends(obter_sessao)) -> PortalLeitura:
    p = servico.portal(sessao)
    categorias = sessao.scalars(select(CategoriaNoticia).where(CategoriaNoticia.ativa.is_(True)).order_by(CategoriaNoticia.ordem, CategoriaNoticia.nome))
    return PortalLeitura(configuracao=ConfiguracaoLeitura.model_validate(p.configuracao, from_attributes=True),
                         slides=[_cartao(n) for n in p.slides], cartoes=[_cartao(n) for n in p.cartoes],
                         atalhos=[_atalho(a) for a in p.atalhos], categorias=[_categoria(c) for c in categorias])


@roteador.get("/portal/atalhos/{atalho_id}/imagem", response_class=FileResponse, summary="Imagem do atalho (pública)",
              responses={**resposta_nao_encontrado("Atalho")})
def imagem_atalho(atalho_id: int, sessao: Session = Depends(obter_sessao)) -> FileResponse:
    atalho = sessao.get(AtalhoPortal, atalho_id)
    anexo = sessao.get(Anexo, atalho.imagem_exibicao_id) if atalho and atalho.imagem_exibicao_id else None
    if anexo is None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Imagem não encontrada.", "nao_encontrado")
    return _inline(anexo, CACHE_PUBLICO)


@roteador.get("/noticias/publicas", response_model=PaginaNoticias, summary="Arquivo de notícias (público)",
              description="Sem login. Só notícias publicadas, das mais recentes às mais antigas. `busca` (título, linha fina e texto), "
                          "`categoria_id`, `ano`, `mes`, `pagina` e `tamanho` (padrão 12, máximo 48).")
def arquivo_publico(busca: str = Query("", max_length=100), categoria_id: int | None = None, ano: int | None = Query(None, ge=2000, le=2100),
                    mes: int | None = Query(None, ge=1, le=12), pagina: int = Query(1, ge=1), tamanho: int = Query(12, ge=1, le=48),
                    sessao: Session = Depends(obter_sessao)) -> PaginaNoticias:
    itens, total = servico.listar_publicas(sessao, busca, categoria_id, ano, mes, pagina, tamanho)
    return PaginaNoticias(itens=[_cartao(n) for n in itens], total=total, pagina=pagina, tamanho=tamanho)


@roteador.get("/noticias/publicas/{slug}", response_model=NoticiaPublica, summary="Notícia publicada (pública)",
              description="Sem login. Conta uma visualização. Rascunhos, notícias em revisão, agendadas ainda não chegadas e arquivadas → 404.",
              responses={**NAO_ENCONTRADA})
def noticia_publica(slug: str, sessao: Session = Depends(obter_sessao)) -> NoticiaPublica:
    with _traduzir():
        n = servico.obter_publica(sessao, slug)
    n.visualizacoes += 1
    sessao.commit()
    base = _cartao(n).model_dump()
    return NoticiaPublica(**base, corpo_html=n.corpo_html, anexos=_arquivos(n, f"/api/noticias/publicas/{n.slug}"),
                          leia_tambem=[_cartao(x) for x in servico.leia_tambem(sessao, n)])


@roteador.get("/noticias/publicas/{slug}/arquivos/{anexo_id}", response_class=FileResponse, summary="Capa ou anexo de notícia publicada (público)",
              responses={**NAO_ENCONTRADA})
def arquivo_de_noticia_publica(slug: str, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao)) -> FileResponse:
    with _traduzir():
        n = servico.obter_publica(sessao, slug)
        anexo = servico.anexo_publico(sessao, n, anexo_id)
    return _inline(anexo, CACHE_PUBLICO)


# ---------------------------------------------------------------------------------------------
# Gestão
# ---------------------------------------------------------------------------------------------

def _gestao_resumo(n: Noticia, agora: datetime) -> dict:
    return dict(id=n.id, slug=n.slug, titulo=n.titulo, situacao=n.situacao, visivel=servico.visivel(n, agora), categoria=_categoria(n.categoria),
                autor_nome=n.autor_nome, publicar_em=_utc(n.publicar_em), atualizado_em=_utc(n.atualizado_em), fixada=n.fixada, capa=_capa_gestao(n))


def _gestao(sessao: Session, usuario: Usuario, n: Noticia) -> NoticiaGestao:
    publico = n.publico_aviso or {}
    usuarios = [u for u in (sessao.get(Usuario, i) for i in publico.get("usuarios_ids") or []) if u]
    setores = [s for s in (sessao.get(Setor, i) for i in publico.get("setores_ids") or []) if s]
    ciencia = None
    if n.aviso_enviado_em:
        total, cientes, _ = servico.ciencias(sessao, n)
        ciencia = CienciaResumo(total=total, cientes=cientes)
    return NoticiaGestao(
        **_gestao_resumo(n, agora_utc()), linha_fina=n.linha_fina, corpo_html=n.corpo_html, categoria_id=n.categoria_id,
        destaque_ate=_utc(n.destaque_ate), exige_ciencia=n.exige_ciencia,
        usuarios_aviso=[Pessoa(id=u.id, nome=u.nome_completo or u.login, login=u.login) for u in usuarios],
        setores_aviso=[SetorResumo(id=s.id, nome=s.nome) for s in setores], aviso_enviado_em=_utc(n.aviso_enviado_em),
        capa_modo=n.capa_modo, capa_recorte=n.capa_recorte, capa_alt=n.capa_alt,
        capa_original=f"/api/noticias/{n.id}/arquivos/{n.capa_anexo_id}" if n.capa_anexo_id else None,
        anexos=_arquivos(n, f"/api/noticias/{n.id}"), autor_id=n.autor_id, enviada_revisao_em=_utc(n.enviada_revisao_em),
        aprovado_por_nome=n.aprovado_por_nome, aprovado_em=_utc(n.aprovado_em), motivo_devolucao=n.motivo_devolucao,
        visualizacoes=n.visualizacoes, ciencia=ciencia, versao=n.versao, acoes=servico.acoes(sessao, usuario, n),
    )


def _dados(d: GravacaoNoticia) -> DadosNoticia:
    return DadosNoticia(titulo=d.titulo, linha_fina=d.linha_fina, corpo_html=d.corpo_html, categoria_id=d.categoria_id, publicar_em=d.publicar_em,
                        destaque_ate=d.destaque_ate, fixada=d.fixada, exige_ciencia=d.exige_ciencia, usuarios_aviso=d.usuarios_aviso,
                        setores_aviso=d.setores_aviso, capa_alt=d.capa_alt)


def _obter_gestao(sessao: Session, usuario: Usuario, noticia_id: uuid.UUID) -> Noticia:
    """Notícia vista na gestão: aprovadores veem todas; redatores, as próprias e as aprovadas/arquivadas."""
    if not servico.eh_redator(sessao, usuario):
        raise ErroNoticia("Você não tem acesso à gestão de notícias.", 403, "sem_permissao")
    n = servico.obter(sessao, noticia_id)
    if not servico.eh_aprovador(sessao, usuario) and n.autor_id != usuario.id and n.situacao not in ("aprovada", "arquivada"):
        raise ErroNoticia("Notícia não encontrada.", 404, "nao_encontrado")
    return n


@roteador.get("/noticias/papel", response_model=PapelNoticias, summary="Meu papel nas notícias",
              description="Nível na ACL `noticias`, se é redator/aprovador, quantas aguardam aprovação e a contagem por situação.",
              responses=RESPOSTAS_AUTENTICADAS)
def papel(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PapelNoticias:
    redator, aprovador = servico.eh_redator(sessao, usuario), servico.eh_aprovador(sessao, usuario)
    contagem = servico.contagem_por_situacao(sessao, usuario) if redator else {}
    return PapelNoticias(nivel=servico.nivel(sessao, usuario), redator=redator, aprovador=aprovador,
                         aguardando_aprovacao=contagem.get("em_revisao", 0) if aprovador else 0, contagem=contagem)


@roteador.get("/noticias", response_model=list[NoticiaGestaoResumo], summary="Notícias (gestão)",
              description="Redator: as próprias e as publicadas/arquivadas. Aprovador: todas. Filtros `situacao` e `busca` (título).",
              responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO})
def listar(situacao: str = Query("", pattern="^(|rascunho|em_revisao|aprovada|devolvida|arquivada)$"), busca: str = Query("", max_length=100),
           sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[NoticiaGestaoResumo]:
    agora = agora_utc()
    with _traduzir():
        return [NoticiaGestaoResumo(**_gestao_resumo(n, agora)) for n in servico.gestao(sessao, usuario, situacao, busca)]


@roteador.post("/noticias", response_model=NoticiaGestao, status_code=status.HTTP_201_CREATED, summary="Criar notícia (rascunho)",
               description="Redator (MODIFICACAO) ou aprovador. O corpo é sanitizado no servidor.", responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **INVALIDO})
def criar(dados: GravacaoNoticia, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    with _traduzir():
        return _gestao(sessao, usuario, servico.criar(sessao, usuario, _dados(dados)))


@roteador.get("/noticias/opcoes-setores", response_model=list[SetorResumo], summary="Setores para o aviso de publicação",
              description="Redator. Setores ativos (o aviso a um setor inclui os setores abaixo dele).", responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO})
def opcoes_setores(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[SetorResumo]:
    with _traduzir():
        if not servico.eh_redator(sessao, usuario):
            raise ErroNoticia("Você não tem acesso à gestão de notícias.", 403, "sem_permissao")
    return [SetorResumo(id=s.id, nome=s.nome) for s in servico.setores_opcoes(sessao)]


@roteador.get("/noticias/opcoes-usuarios", response_model=list[Pessoa], summary="Usuários para o aviso de publicação",
              description="Redator. Usuários ativos por nome ou login (`busca`, até 20).", responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO})
def opcoes_usuarios(busca: str = Query("", max_length=100), sessao: Session = Depends(obter_sessao),
                    usuario: Usuario = Depends(obter_usuario_atual)) -> list[Pessoa]:
    from sqlalchemy import func
    with _traduzir():
        if not servico.eh_redator(sessao, usuario):
            raise ErroNoticia("Você não tem acesso à gestão de notícias.", 403, "sem_permissao")
    termo = f"%{busca.strip().lower()}%"
    lista = sessao.scalars(select(Usuario).where(Usuario.ativo.is_(True), func.lower(Usuario.nome_completo + " " + Usuario.login).like(termo))
                           .order_by(Usuario.nome_completo).limit(20))
    return [Pessoa(id=u.id, nome=u.nome_completo or u.login, login=u.login) for u in lista]


@roteador.get("/noticias/categorias", response_model=list[CategoriaLeitura], summary="Categorias (todas, inclusive inativas)",
              responses=RESPOSTAS_AUTENTICADAS)
def categorias(sessao: Session = Depends(obter_sessao), _usuario: Usuario = Depends(obter_usuario_atual)) -> list[CategoriaLeitura]:
    return [_categoria(c) for c in sessao.scalars(select(CategoriaNoticia).order_by(CategoriaNoticia.ordem, CategoriaNoticia.nome))]


@roteador.post("/noticias/categorias", response_model=CategoriaLeitura, status_code=status.HTTP_201_CREATED, summary="Criar categoria",
               description="Aprovador.", responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **CONFLITO})
def criar_categoria(dados: GravacaoCategoria, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> CategoriaLeitura:
    with _traduzir():
        return _categoria(servico.salvar_categoria(sessao, usuario, None, dados.nome, dados.cor, dados.ordem, dados.ativa))


@roteador.put("/noticias/categorias/{categoria_id}", response_model=CategoriaLeitura, summary="Alterar categoria",
              description="Aprovador. Para tirar de uso, marque `ativa = false` (as notícias continuam com ela).",
              responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **CONFLITO, **resposta_nao_encontrado("Categoria")})
def alterar_categoria(categoria_id: int, dados: GravacaoCategoria, sessao: Session = Depends(obter_sessao),
                      usuario: Usuario = Depends(obter_usuario_atual)) -> CategoriaLeitura:
    with _traduzir():
        return _categoria(servico.salvar_categoria(sessao, usuario, categoria_id, dados.nome, dados.cor, dados.ordem, dados.ativa))


@roteador.get("/noticias/{noticia_id}", response_model=NoticiaGestao, summary="Notícia (gestão)",
              responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA})
def detalhe(noticia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    with _traduzir():
        return _gestao(sessao, usuario, _obter_gestao(sessao, usuario, noticia_id))


@roteador.put("/noticias/{noticia_id}", response_model=NoticiaGestao, summary="Editar notícia",
              description="Redator: os próprios rascunhos e devolvidas. Aprovador: qualquer uma (menos arquivada). `versao` evita sobrescrever.",
              responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA, **INVALIDO, **CONFLITO})
def editar(noticia_id: uuid.UUID, dados: GravacaoNoticia, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    with _traduzir():
        n = _obter_gestao(sessao, usuario, noticia_id)
        return _gestao(sessao, usuario, servico.editar(sessao, usuario, n, _dados(dados), dados.versao))


@roteador.delete("/noticias/{noticia_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir notícia",
                 description="Autor (rascunho/devolvida), aprovador (não publicada) ou SuperRoot.", responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA})
def excluir(noticia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        servico.excluir(sessao, usuario, _obter_gestao(sessao, usuario, noticia_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/noticias/{noticia_id}/enviar-revisao", response_model=NoticiaGestao, summary="Enviar para aprovação",
               description="Exige título, texto, capa e texto alternativo. Avisa os aprovadores (caixa + e-mail); `publicar_em` vazio = imediata.",
               responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA, **INVALIDO})
def enviar_revisao(noticia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    with _traduzir():
        return _gestao(sessao, usuario, servico.enviar_revisao(sessao, usuario, _obter_gestao(sessao, usuario, noticia_id)))


@roteador.post("/noticias/{noticia_id}/aprovar", response_model=NoticiaGestao, summary="Aprovar e publicar",
               description="Aprovador. Publica agora ou na data pedida (`publicar_em` opcional ajusta). Avisa o autor; se já estiver no portal, "
                           "dispara o aviso ao público escolhido.", responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA, **INVALIDO})
def aprovar(noticia_id: uuid.UUID, dados: Aprovacao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    with _traduzir():
        return _gestao(sessao, usuario, servico.aprovar(sessao, usuario, _obter_gestao(sessao, usuario, noticia_id), dados.publicar_em))


@roteador.post("/noticias/{noticia_id}/devolver", response_model=NoticiaGestao, summary="Devolver para ajustes",
               description="Aprovador; motivo obrigatório (vai ao autor).", responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA, **INVALIDO})
def devolver(noticia_id: uuid.UUID, dados: Devolucao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    with _traduzir():
        return _gestao(sessao, usuario, servico.devolver(sessao, usuario, _obter_gestao(sessao, usuario, noticia_id), dados.motivo))


@roteador.post("/noticias/{noticia_id}/arquivar", response_model=NoticiaGestao, summary="Arquivar (tirar do portal)",
               responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA})
def arquivar(noticia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    with _traduzir():
        return _gestao(sessao, usuario, servico.arquivar(sessao, usuario, _obter_gestao(sessao, usuario, noticia_id), True))


@roteador.post("/noticias/{noticia_id}/desarquivar", response_model=NoticiaGestao, summary="Desarquivar (volta ao portal)",
               responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA})
def desarquivar(noticia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    with _traduzir():
        return _gestao(sessao, usuario, servico.arquivar(sessao, usuario, _obter_gestao(sessao, usuario, noticia_id), False))


@roteador.post("/noticias/{noticia_id}/capa", response_model=NoticiaGestao, summary="Capa: enviar imagem e/ou recortar",
               description="`multipart/form-data`: `arquivo` (JPG, PNG ou WebP até 15 MB; opcional se só mudar o recorte), `modo` (`recortar` | `inteira`) "
                           "e `recorte` (JSON `{x, y, largura, altura}` em pixels do original; ajustado para 2:1). Gera as versões WebP 1600, 800 e 400.",
               responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA, **INVALIDO})
async def capa(noticia_id: uuid.UUID, modo: str = Form("recortar"), recorte: str = Form(""), arquivo: UploadFile | None = File(None),
               sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    conteudo = await arquivo.read() if arquivo is not None else None
    try:
        caixa = json.loads(recorte) if recorte.strip() else None
    except ValueError as erro:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "Recorte inválido.", "invalido") from erro
    with _traduzir():
        n = _obter_gestao(sessao, usuario, noticia_id)
        n = servico.definir_capa(sessao, usuario, n, conteudo, arquivo.filename if arquivo else "", modo, caixa)
        return _gestao(sessao, usuario, n)


@roteador.post("/noticias/{noticia_id}/anexos", response_model=NoticiaGestao, summary="Anexar arquivo",
               description="`multipart/form-data` com `arquivo` (PDF, Office/LibreOffice, TXT, CSV, PNG, JPG; até 10 por notícia).",
               responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA, **INVALIDO})
async def anexar(noticia_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
                 usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    conteudo = await arquivo.read()
    with _traduzir():
        n = servico.anexar(sessao, usuario, _obter_gestao(sessao, usuario, noticia_id), conteudo, arquivo.filename or "arquivo")
        return _gestao(sessao, usuario, n)


@roteador.delete("/noticias/{noticia_id}/anexos/{anexo_id}", response_model=NoticiaGestao, summary="Remover anexo",
                 responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **NAO_ENCONTRADA})
def remover_anexo(noticia_id: uuid.UUID, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao),
                  usuario: Usuario = Depends(obter_usuario_atual)) -> NoticiaGestao:
    with _traduzir():
        return _gestao(sessao, usuario, servico.remover_anexo(sessao, usuario, _obter_gestao(sessao, usuario, noticia_id), anexo_id))


@roteador.get("/noticias/{noticia_id}/arquivos/{anexo_id}", response_class=FileResponse, summary="Arquivo da notícia (gestão)",
              description="Capa original, versões da capa ou anexos, para quem vê a notícia na gestão.", responses={**RESPOSTAS_AUTENTICADAS, **NAO_ENCONTRADA})
def arquivo_gestao(noticia_id: uuid.UUID, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao),
                   usuario: Usuario = Depends(obter_usuario_atual)) -> FileResponse:
    with _traduzir():
        n = _obter_gestao(sessao, usuario, noticia_id)
        if n.capa_anexo_id == anexo_id:
            anexo = sessao.get(Anexo, anexo_id)
        else:
            anexo = servico.anexo_publico(sessao, n, anexo_id)
    return _inline(anexo)


@roteador.get("/noticias/{noticia_id}/revisoes", response_model=list[RevisaoLeitura], summary="Histórico de versões",
              responses={**RESPOSTAS_AUTENTICADAS, **NAO_ENCONTRADA})
def revisoes(noticia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[RevisaoLeitura]:
    with _traduzir():
        n = _obter_gestao(sessao, usuario, noticia_id)
    lista = sessao.scalars(select(RevisaoNoticia).where(RevisaoNoticia.noticia_id == n.id).order_by(RevisaoNoticia.criado_em.desc()))
    return [RevisaoLeitura(versao=r.versao, descricao=r.descricao, titulo=r.titulo, linha_fina=r.linha_fina, corpo_html=r.corpo_html,
                           autor_nome=r.autor_nome, criado_em=_utc(r.criado_em)) for r in lista]


@roteador.get("/noticias/{noticia_id}/ciencias", response_model=CienciaLeitura, summary="Quem recebeu o aviso e deu ciência",
              responses={**RESPOSTAS_AUTENTICADAS, **NAO_ENCONTRADA})
def ciencias(noticia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> CienciaLeitura:
    with _traduzir():
        n = _obter_gestao(sessao, usuario, noticia_id)
    total, cientes, pessoas = servico.ciencias(sessao, n)
    return CienciaLeitura(total=total, cientes=cientes, pessoas=[PessoaCiencia(nome=p, ciente_em=c) for p, c in pessoas])


# ---------------------------------------------------------------------------------------------
# Configuração do portal e atalhos (aprovadores)
# ---------------------------------------------------------------------------------------------

@roteador.get("/portal/configuracao", response_model=ConfiguracaoGestao, summary="Configuração do portal (gestão)",
              description="Parâmetros do slider, a curadoria atual e as notícias publicadas recentes para escolher.", responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO})
def obter_configuracao(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> ConfiguracaoGestao:
    with _traduzir():
        if not servico.eh_aprovador(sessao, usuario):
            raise ErroNoticia("Só aprovadores configuram o portal.", 403, "sem_permissao")
    agora = agora_utc()
    config = servico.configuracao(sessao)
    curadoria = sessao.scalars(select(Noticia).where(Noticia.ordem_slider.is_not(None)).order_by(Noticia.ordem_slider))
    candidatas, _ = servico.listar_publicas(sessao, tamanho=40, agora=agora)
    return ConfiguracaoGestao(configuracao=ConfiguracaoLeitura.model_validate(config, from_attributes=True),
                              curadoria=[_cartao(n) for n in curadoria if servico.visivel(n, agora)], candidatas=[_cartao(n) for n in candidatas])


@roteador.put("/portal/configuracao", response_model=ConfiguracaoGestao, summary="Salvar configuração do portal",
              description="Aprovador. Com `curadoria`, grava a ordem manual do slider (as notícias fora da lista saem da curadoria).",
              responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO})
def salvar_configuracao(dados: GravacaoConfiguracao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> ConfiguracaoGestao:
    campos = dados.model_dump(exclude={"curadoria"})
    with _traduzir():
        servico.salvar_configuracao(sessao, usuario, campos, dados.curadoria)
    return obter_configuracao(sessao, usuario)


@roteador.get("/portal/atalhos", response_model=list[AtalhoLeitura], summary="Atalhos (todos, gestão)", responses=RESPOSTAS_AUTENTICADAS)
def atalhos(sessao: Session = Depends(obter_sessao), _usuario: Usuario = Depends(obter_usuario_atual)) -> list[AtalhoLeitura]:
    return [_atalho(a) for a in sessao.scalars(select(AtalhoPortal).order_by(AtalhoPortal.ordem, AtalhoPortal.id))]


@roteador.post("/portal/atalhos", response_model=AtalhoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar atalho",
               description="Aprovador. `multipart/form-data`: `titulo`, `url`, `ativo`, `nova_aba` e `imagem` (JPG, PNG ou WebP).",
               responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **INVALIDO})
async def criar_atalho(titulo: str = Form(..., min_length=1, max_length=80), url: str = Form(..., pattern=r"^(https?://|/).+", max_length=500),
                       ativo: bool = Form(True), nova_aba: bool = Form(True), imagem: UploadFile | None = File(None),
                       sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> AtalhoLeitura:
    conteudo = await imagem.read() if imagem is not None else None
    with _traduzir():
        return _atalho(servico.salvar_atalho(sessao, usuario, None, titulo, url, ativo, nova_aba, conteudo, imagem.filename if imagem else ""))


@roteador.put("/portal/atalhos/{atalho_id}", response_model=AtalhoLeitura, summary="Alterar atalho",
              description="Aprovador. Mesmos campos da criação; `imagem` opcional (sem ela, mantém a atual).",
              responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Atalho")})
async def alterar_atalho(atalho_id: int, titulo: str = Form(..., min_length=1, max_length=80), url: str = Form(..., pattern=r"^(https?://|/).+", max_length=500),
                         ativo: bool = Form(True), nova_aba: bool = Form(True), imagem: UploadFile | None = File(None),
                         sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> AtalhoLeitura:
    conteudo = await imagem.read() if imagem is not None else None
    with _traduzir():
        return _atalho(servico.salvar_atalho(sessao, usuario, atalho_id, titulo, url, ativo, nova_aba, conteudo, imagem.filename if imagem else ""))


@roteador.delete("/portal/atalhos/{atalho_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir atalho",
                 responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO, **resposta_nao_encontrado("Atalho")})
def excluir_atalho(atalho_id: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        servico.excluir_atalho(sessao, usuario, atalho_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/portal/atalhos/ordem", status_code=status.HTTP_204_NO_CONTENT, summary="Reordenar atalhos",
               responses={**RESPOSTAS_AUTENTICADAS, **SEM_PERMISSAO})
def ordenar_atalhos(dados: Reordenacao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        servico.ordenar_atalhos(sessao, usuario, dados.ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
