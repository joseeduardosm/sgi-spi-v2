# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de login, sessão e perfil do próprio usuário.
"""Rotas de autenticação (`/api/autenticacao`).

- `POST /login`: troca login e senha por um token JWT;
- `GET /sessao`: quem é o dono do token;
- `GET/PUT /perfil`: o próprio perfil institucional.

As rotas de sessão e perfil usam `obter_usuario_autenticado` (e não `obter_usuario_atual`) porque
precisam funcionar mesmo quando o perfil está pendente: é por elas que o usuário regulariza o cadastro.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_autenticado
from app.api.respostas import INVALIDO, VALIDACAO, erro_regra
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.usuario import Usuario
from app.schemas.autenticacao import RequisicaoLogin, RespostaToken, UsuarioSessao
from app.schemas.comum import RespostaErro
from app.schemas.usuarios import OpcaoUsuario, PerfilLeitura, RevisaoPerfil
from app.services import servico_admin_usuarios
from app.services.servico_admin_usuarios import ErroRegraUsuario
from app.services.servico_autenticacao import ServicoAutenticacao, para_usuario_sessao

roteador = APIRouter(prefix="/autenticacao", tags=["Autenticação"], responses=VALIDACAO)

# Descrição do 401 para a documentação das rotas que exigem token
NAO_AUTENTICADO = {status.HTTP_401_UNAUTHORIZED: {"model": RespostaErro, "description": "Token ausente, inválido ou expirado."}}


@roteador.post(
    "/login",
    response_model=RespostaToken,
    summary="Autenticar usuário",
    description=(
        "Valida login e senha e emite um token JWT de acesso. Com um diretório LDAP ativo, tenta primeiro a "
        "autenticação corporativa; se ela falhar ou o diretório estiver indisponível, tenta a conta local."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"model": RespostaErro, "description": "Usuário ou senha inválidos."}},
)
def entrar(dados: RequisicaoLogin, sessao: Session = Depends(obter_sessao)) -> RespostaToken:
    """Autentica e devolve o token. A mensagem de erro é a mesma para login e senha errados (não revela qual)."""
    servico = ServicoAutenticacao(sessao)
    usuario = servico.autenticar(dados.login, dados.senha)
    if usuario is None:
        raise ErroApi(status.HTTP_401_UNAUTHORIZED, "Usuário ou senha inválidos.", "nao_autenticado")
    return servico.emitir_token(usuario)


@roteador.get(
    "/sessao",
    response_model=UsuarioSessao,
    summary="Usuário autenticado",
    description=(
        "Retorna os dados do usuário dono do token, incluindo a situação do perfil institucional "
        "(`perfil_restrito`). Funciona mesmo com o perfil pendente."
    ),
    responses=NAO_AUTENTICADO,
)
def obter_sessao_atual(usuario: Usuario = Depends(obter_usuario_autenticado)) -> UsuarioSessao:
    """Dados do usuário logado; o frontend chama ao abrir para confirmar que o token ainda vale."""
    return para_usuario_sessao(usuario)


@roteador.get(
    "/perfil",
    response_model=PerfilLeitura,
    summary="Meu perfil institucional",
    description="Perfil do usuário autenticado. Funciona mesmo com o perfil pendente.",
    responses=NAO_AUTENTICADO,
)
def obter_meu_perfil(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado)) -> PerfilLeitura:
    """Perfil institucional do próprio usuário (reaproveita o detalhe completo e devolve só o perfil)."""
    return servico_admin_usuarios.para_detalhe(sessao, usuario).perfil


@roteador.put(
    "/perfil",
    response_model=UsuarioSessao,
    summary="Atualizar e revalidar meu perfil",
    description=(
        "Grava o perfil institucional e registra a revalidação (reinicia o prazo de 30 dias). "
        "Exige nome completo, e-mail, ramal, cargo, departamento, andar e prédio. "
        "Retorna a sessão atualizada, com `perfil_restrito` recalculado."
    ),
    responses={**NAO_AUTENTICADO, **INVALIDO},
)
def revisar_meu_perfil(
    dados: RevisaoPerfil, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado)
) -> UsuarioSessao:
    """Grava o perfil; em caso de regra violada, desfaz a transação e responde 400/409."""
    try:
        return para_usuario_sessao(servico_admin_usuarios.revisar_proprio_perfil(sessao, usuario, dados))
    except ErroRegraUsuario as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)


@roteador.get(
    "/perfil/opcoes-gestor",
    response_model=list[OpcaoUsuario],
    summary="Opções de gestor imediato",
    description="Usuários ativos para o seletor de gestor do próprio perfil. Funciona mesmo com o perfil pendente.",
    responses=NAO_AUTENTICADO,
)
def listar_opcoes_gestor(
    busca: str | None = Query(None, max_length=100),
    limite: int = Query(20, ge=1, le=50),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(obter_usuario_autenticado),
) -> list[OpcaoUsuario]:
    """Busca de usuários para escolher o gestor imediato, sem exigir acesso ao módulo Usuários."""
    return servico_admin_usuarios.opcoes(sessao, busca, limite)
