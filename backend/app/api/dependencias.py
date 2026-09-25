"""Dependências compartilhadas pelas rotas (banco, autenticação e autorização)."""

from collections.abc import Callable

import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.core.seguranca import decodificar_token_acesso
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.services import servico_acl, servico_perfil

esquema_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="TokenBearer",
    description="JWT obtido em `POST /api/autenticacao/login`.",
)


def _nao_autenticado(detalhe: str) -> ErroApi:
    return ErroApi(status.HTTP_401_UNAUTHORIZED, detalhe, "nao_autenticado")


def obter_usuario_autenticado(
    credenciais: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    sessao: Session = Depends(obter_sessao),
) -> Usuario:
    """Usuário do token, sem verificar o perfil institucional.

    Use apenas nos endpoints que devem funcionar durante a atualização obrigatória do perfil
    (sessão e próprio perfil). Os demais usam `obter_usuario_atual`.
    """
    if credenciais is None:
        raise _nao_autenticado("Não autenticado.")
    try:
        conteudo = decodificar_token_acesso(credenciais.credentials)
    except jwt.ExpiredSignatureError:
        raise _nao_autenticado("Sessão expirada.")
    except jwt.InvalidTokenError:
        raise _nao_autenticado("Token inválido.")

    try:
        usuario = sessao.get(Usuario, int(conteudo["sub"]))
    except (TypeError, ValueError):
        raise _nao_autenticado("Token inválido.")
    if usuario is None or not usuario.ativo:
        raise _nao_autenticado("Usuário inválido ou inativo.")
    return usuario


def obter_usuario_atual(usuario: Usuario = Depends(obter_usuario_autenticado)) -> Usuario:
    """Usuário autenticado com perfil institucional em dia (SuperRoot não passa por essa restrição)."""
    if servico_perfil.perfil_restrito(usuario):
        raise ErroApi(
            status.HTTP_403_FORBIDDEN,
            "Atualize seu cadastro para continuar usando o sistema.",
            "revisao_perfil_obrigatoria",
            campos_pendentes=servico_perfil.campos_pendentes(usuario),
        )
    return usuario


def exigir_papeis(*papeis: str) -> Callable[..., Usuario]:
    """Exige que o usuário autenticado possua ao menos um dos papéis informados.

    Uso: `usuario: Usuario = Depends(exigir_papeis(Papel.SUPER_ROOT))`.
    """

    def verificar(usuario: Usuario = Depends(obter_usuario_atual)) -> Usuario:
        if not any(usuario.possui_papel(p) for p in papeis):
            raise ErroApi(status.HTTP_403_FORBIDDEN, "Acesso negado.", "acesso_negado")
        return usuario

    return verificar


def exigir_acl(recurso: str, nivel_minimo: str = NivelAcl.LEITURA) -> Callable[..., Usuario]:
    """Exige nível de ACL mínimo no recurso (slug) antes de executar o endpoint.

    Uso: `usuario: Usuario = Depends(exigir_acl("usuarios", NivelAcl.MODIFICACAO))`.
    Sem nível suficiente → 403 com `codigo = acl_negado`, recurso, nível exigido e efetivo.
    """

    def verificar(usuario: Usuario = Depends(obter_usuario_atual), sessao: Session = Depends(obter_sessao)) -> Usuario:
        efetivo = servico_acl.resolver_acesso(sessao, usuario, recurso)
        if NivelAcl.posicao(efetivo) < NivelAcl.posicao(nivel_minimo):
            raise ErroApi(
                status.HTTP_403_FORBIDDEN,
                f"Você não possui o nível de acesso necessário para este recurso. "
                f"Esta operação exige {nivel_minimo} em '{recurso}'; seu acesso efetivo é {efetivo or 'nenhum'}.",
                "acl_negado",
                recurso=recurso,
                nivel_exigido=nivel_minimo,
                nivel_efetivo=efetivo,
            )
        return usuario

    return verificar
