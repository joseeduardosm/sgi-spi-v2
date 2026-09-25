# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de controle de acesso (recursos, regras e acessos efetivos).

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis, obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, erro_regra, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.models.usuario import Papel, Usuario
from app.schemas.acl import AcessoEfetivo, GravacaoRecurso, GravacaoRegra, LeituraRecurso, LeituraRegra
from app.services import servico_acl
from app.services import servico_admin_acl as servico
from app.services.servico_admin_acl import AclNaoEncontrado, ErroRegraAcl

roteador = APIRouter(prefix="/acl", tags=["Controle de acesso (ACL)"], responses=RESPOSTAS_AUTENTICADAS)

super_root = exigir_papeis(Papel.SUPER_ROOT)


def _efetivos(sessao: Session, usuario: Usuario, somente_concedidos: bool) -> list[AcessoEfetivo]:
    return [
        AcessoEfetivo(recurso_id=r.id, nome=r.nome, slug=r.slug, url_base=r.url_base, nivel=nivel)
        for r, nivel in servico_acl.acessos_efetivos(sessao, usuario)
        if nivel is not None or not somente_concedidos
    ]


@roteador.get(
    "/meus-acessos",
    response_model=list[AcessoEfetivo],
    summary="Meus acessos efetivos",
    description="Recursos ativos aos quais o usuário autenticado tem acesso, com o nível efetivo. Usado pelo frontend para ocultar módulos.",
)
def listar_meus_acessos(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[AcessoEfetivo]:
    return _efetivos(sessao, usuario, somente_concedidos=True)


@roteador.get(
    "/efetivo/{usuario_id}",
    response_model=list[AcessoEfetivo],
    summary="Acesso efetivo de um usuário",
    description="Nível efetivo do usuário em cada recurso ativo (`nivel` nulo = sem acesso). Restrito ao SuperRoot.",
    responses=resposta_nao_encontrado("Usuário"),
)
def consultar_acesso_efetivo(usuario_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> list[AcessoEfetivo]:
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise nao_encontrado("Usuário")
    return _efetivos(sessao, usuario, somente_concedidos=False)


# --- Recursos -------------------------------------------------------------------

@roteador.get("/recursos", response_model=list[LeituraRecurso], summary="Listar recursos", description="Restrito ao SuperRoot.")
def listar_recursos(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> list[LeituraRecurso]:
    return servico.listar_recursos(sessao)


@roteador.post(
    "/recursos",
    response_model=LeituraRecurso,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar recurso",
    description="O slug é normalizado (minúsculas, `a-z0-9_-`). Nome e slug são únicos. Restrito ao SuperRoot.",
    responses={**CONFLITO, **INVALIDO},
)
def criar_recurso(dados: GravacaoRecurso, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> LeituraRecurso:
    try:
        recurso = servico.gravar_recurso(sessao, dados, autor.login)
    except ErroRegraAcl as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)
    return servico.ler_recurso(sessao, recurso.id)


@roteador.put(
    "/recursos/{recurso_id}",
    response_model=LeituraRecurso,
    summary="Alterar recurso",
    description="Restrito ao SuperRoot.",
    responses={**resposta_nao_encontrado("Recurso"), **CONFLITO, **INVALIDO},
)
def alterar_recurso(recurso_id: int, dados: GravacaoRecurso, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> LeituraRecurso:
    try:
        servico.gravar_recurso(sessao, dados, autor.login, recurso_id)
    except AclNaoEncontrado:
        raise nao_encontrado("Recurso")
    except ErroRegraAcl as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)
    return servico.ler_recurso(sessao, recurso_id)


@roteador.delete(
    "/recursos/{recurso_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir recurso",
    description="Exclui o recurso e suas regras; o módulo volta a ficar aberto. Restrito ao SuperRoot.",
    responses=resposta_nao_encontrado("Recurso"),
)
def excluir_recurso(recurso_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> Response:
    try:
        servico.excluir_recurso(sessao, recurso_id, autor.login)
    except AclNaoEncontrado:
        raise nao_encontrado("Recurso")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Regras ---------------------------------------------------------------------

@roteador.get("/regras", response_model=list[LeituraRegra], summary="Listar regras", description="Restrito ao SuperRoot.")
def listar_regras(
    recurso_id: int | None = Query(None, description="Filtra pelo recurso."),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(super_root),
) -> list[LeituraRegra]:
    return servico.listar_regras(sessao, recurso_id)


@roteador.post(
    "/regras",
    response_model=LeituraRegra,
    status_code=status.HTTP_201_CREATED,
    summary="Criar regra",
    description="Associa um nível a usuários e/ou setores. A primeira regra de um recurso o torna lista positiva. Restrito ao SuperRoot.",
    responses=INVALIDO,
)
def criar_regra(dados: GravacaoRegra, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> LeituraRegra:
    try:
        return servico.para_leitura_regra(servico.gravar_regra(sessao, dados, autor.login))
    except ErroRegraAcl as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)


@roteador.put(
    "/regras/{regra_id}",
    response_model=LeituraRegra,
    summary="Alterar regra",
    description="Restrito ao SuperRoot.",
    responses={**resposta_nao_encontrado("Regra"), **INVALIDO},
)
def alterar_regra(regra_id: int, dados: GravacaoRegra, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> LeituraRegra:
    try:
        return servico.para_leitura_regra(servico.gravar_regra(sessao, dados, autor.login, regra_id))
    except AclNaoEncontrado:
        raise nao_encontrado("Regra")
    except ErroRegraAcl as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)


@roteador.delete(
    "/regras/{regra_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir regra",
    description="Restrito ao SuperRoot.",
    responses=resposta_nao_encontrado("Regra"),
)
def excluir_regra(regra_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> Response:
    try:
        servico.excluir_regra(sessao, regra_id, autor.login)
    except AclNaoEncontrado:
        raise nao_encontrado("Regra")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
