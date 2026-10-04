# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do Diretório: ramais em cartões, aniversariantes, mural de parabéns, favoritos e foto.
"""Rotas `/api/diretorio`. Qualquer usuário logado consulta; cada um altera apenas a própria foto, os favoritos e os próprios recados."""

from contextlib import contextmanager
from io import BytesIO

import segno
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.usuario import Usuario
from app.schemas.diretorio import (
    AlteracaoPreferencias, Aniversariante, ContatoDetalhe, GravacaoParabens, OpcoesFiltro, PaginaContatos, Parabens, Preferencias,
)
from app.services import servico_anexos
from app.services import servico_diretorio as servico
from app.services.servico_diretorio import ErroDiretorio, FiltrosRamais

roteador = APIRouter(prefix="/diretorio", tags=["Diretório"], responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADO = resposta_nao_encontrado("Contato, aniversariante ou foto")
LIMITE_UPLOAD = 6 * 1024 * 1024


@contextmanager
def _traduzir(sessao: Session | None = None):
    """Converte `ErroDiretorio` no erro padrão da API."""
    try:
        yield
    except ErroDiretorio as erro:
        if sessao is not None:
            sessao.rollback()
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _preferencias(u: Usuario) -> Preferencias:
    return Preferencias(foto_url=servico.foto_url(u), foto_origem=u.foto_origem if u.foto_anexo_id else None, ocultar_aniversario=u.ocultar_aniversario)


@roteador.get("/ramais", response_model=PaginaContatos, summary="Listar ramais (cartões de visita)", responses={**INVALIDO})
def listar_ramais(
    q: str = Query("", max_length=100, description="Busca em nome, cargo, setor, ramal, e-mail, andar e prédio (sem acento, várias palavras)."),
    setor: str | None = Query(None, max_length=150), andar: str | None = Query(None, max_length=30), predio: str | None = Query(None, max_length=100),
    favoritos: bool = Query(False, description="Só os contatos fixados."), em_ferias: bool = Query(False, description="Só quem está de férias hoje."),
    pagina: int = Query(1, ge=1), tamanho: int = Query(24, ge=1, le=200),
    sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual),
) -> PaginaContatos:
    """Usuários ativos com nome e ramal. Favoritos vêm primeiro; quem está de férias aprovadas hoje traz `ferias_inicio`/`ferias_fim` (o selo some sozinho no fim)."""
    return servico.listar_ramais(sessao, usuario, FiltrosRamais(q, setor, andar, predio, favoritos, em_ferias), pagina, tamanho)


@roteador.get("/filtros", response_model=OpcoesFiltro, summary="Opções dos filtros de ramais")
def opcoes_filtro(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> OpcoesFiltro:
    """Setores, andares e prédios existentes, para montar os filtros da tela."""
    return servico.opcoes_filtro(sessao)


@roteador.get("/ramais/{contato_id}", response_model=ContatoDetalhe, summary="Detalhar um contato", responses=NAO_ENCONTRADO)
def detalhar(contato_id: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> ContatoDetalhe:
    """Cartão completo, com a chefia imediata e a equipe (quem tem esta pessoa como gestor)."""
    with _traduzir():
        return servico.detalhe_contato(sessao, usuario, contato_id)


@roteador.get("/ramais/{contato_id}/vcard", summary="Baixar o contato em vCard", responses={**NAO_ENCONTRADO, 200: {"content": {"text/vcard": {}}, "description": "Arquivo .vcf."}})
def baixar_vcard(contato_id: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    """Cartão em vCard 3.0, aceito por celulares e pelo Outlook."""
    with _traduzir():
        alvo = servico.obter_contato(sessao, usuario, contato_id)
    nome = servico_anexos.nome_seguro(alvo.nome_completo or alvo.login)
    return Response(servico.vcard(alvo), media_type="text/vcard; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{nome}.vcf"'})


@roteador.get("/ramais/{contato_id}/qrcode", summary="QR Code do contato", responses={**NAO_ENCONTRADO, 200: {"content": {"image/png": {}}, "description": "PNG com o vCard."}})
def qrcode_contato(contato_id: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    """PNG de um QR Code que traz o vCard: a câmera do celular oferece salvar o contato."""
    with _traduzir():
        alvo = servico.obter_contato(sessao, usuario, contato_id)
    saida = BytesIO()
    segno.make(servico.vcard(alvo), error="m").save(saida, kind="png", scale=6, border=2)
    return Response(saida.getvalue(), media_type="image/png")


@roteador.put("/favoritos/{contato_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Fixar contato nos favoritos", responses=NAO_ENCONTRADO)
def favoritar(contato_id: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    """Idempotente: fixar um contato já fixado não faz nada."""
    with _traduzir():
        servico.alternar_favorito(sessao, usuario, contato_id, True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.delete("/favoritos/{contato_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remover contato dos favoritos", responses=NAO_ENCONTRADO)
def desfavoritar(contato_id: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    """Idempotente."""
    with _traduzir():
        servico.alternar_favorito(sessao, usuario, contato_id, False)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/aniversariantes", response_model=list[Aniversariante], summary="Listar aniversariantes")
def aniversariantes(
    periodo: str = Query("semana", pattern="^(dia|semana|mes)$", description="`dia` (hoje), `semana` (hoje + 6 dias) ou `mes`."),
    sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual),
) -> list[Aniversariante]:
    """Quem faz aniversário no período, sem o ano de nascimento. Quem optou por ocultar não aparece."""
    return servico.listar_aniversariantes(sessao, usuario, periodo)


@roteador.get("/aniversariantes/{aniversariante_id}/parabens", response_model=list[Parabens], summary="Ler o mural de parabéns", responses=NAO_ENCONTRADO)
def ler_mural(aniversariante_id: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[Parabens]:
    """Recados do aniversário mais próximo de hoje, do mais antigo ao mais novo."""
    with _traduzir():
        return servico.mural(sessao, usuario, aniversariante_id)


@roteador.post(
    "/aniversariantes/{aniversariante_id}/parabens", response_model=Parabens, status_code=status.HTTP_201_CREATED, summary="Deixar recado no mural",
    responses={**NAO_ENCONTRADO, **INVALIDO, **CONFLITO},
)
def parabenizar(
    aniversariante_id: int, dados: GravacaoParabens, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual),
) -> Parabens:
    """Um recado por pessoa e por ano, de 7 dias antes a 7 dias depois do aniversário (400 fora da janela ou no próprio mural). O aniversariante recebe um aviso."""
    with _traduzir(sessao):
        return servico.parabenizar(sessao, usuario, aniversariante_id, dados.texto)


@roteador.delete("/aniversariantes/{aniversariante_id}/parabens", status_code=status.HTTP_204_NO_CONTENT, summary="Apagar o próprio recado", responses=NAO_ENCONTRADO)
def apagar_recado(aniversariante_id: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    """Apaga o recado do usuário logado no mural do aniversário corrente."""
    with _traduzir(sessao):
        servico.apagar_parabens(sessao, usuario, aniversariante_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/preferencias", response_model=Preferencias, summary="Minhas preferências do diretório")
def minhas_preferencias(usuario: Usuario = Depends(obter_usuario_atual)) -> Preferencias:
    """Foto atual e se o usuário oculta o próprio aniversário."""
    return _preferencias(usuario)


@roteador.patch("/preferencias", response_model=Preferencias, summary="Ocultar ou mostrar meu aniversário")
def alterar_preferencias(
    dados: AlteracaoPreferencias, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)
) -> Preferencias:
    """Opt-out (LGPD): com `ocultar_aniversario = true` a pessoa some das listas e do mural e deixa de receber o parabéns automático."""
    usuario.ocultar_aniversario = dados.ocultar_aniversario
    sessao.commit()
    return _preferencias(usuario)


@roteador.put("/foto", response_model=Preferencias, summary="Enviar minha foto", responses=INVALIDO)
def enviar_foto(
    arquivo: UploadFile = File(..., description="PNG ou JPG de até 5 MB. É recortada em quadrado e reduzida a 400 px."),
    sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual),
) -> Preferencias:
    """Substitui a foto do cartão. Uma foto enviada aqui não é sobrescrita pela sincronização com o LDAP."""
    dados = arquivo.file.read(LIMITE_UPLOAD + 1)
    with _traduzir(sessao):
        servico.definir_foto(sessao, usuario, dados, "upload", usuario.id)
    sessao.commit()
    return _preferencias(usuario)


@roteador.delete("/foto", response_model=Preferencias, summary="Remover minha foto")
def remover_foto(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Preferencias:
    """Remove a foto; o cartão volta a mostrar as iniciais e o LDAP não a repõe."""
    servico.remover_foto(sessao, usuario)
    return _preferencias(usuario)


@roteador.get("/fotos/{contato_id}", summary="Foto de um contato", response_class=FileResponse, responses=NAO_ENCONTRADO)
def foto(contato_id: int, v: str | None = Query(None, description="Versão da foto, só para o cache do navegador."),
         sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> FileResponse:
    """Imagem JPEG 400×400. Exige login; o navegador pode guardar em cache por 1 dia."""
    with _traduzir():
        anexo = servico.anexo_da_foto(sessao, contato_id)
    try:
        resposta = servico_anexos.resposta_download(anexo)
    except servico_anexos.ErroAnexo as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro
    resposta.headers["Cache-Control"] = "private, max-age=86400"
    return resposta
