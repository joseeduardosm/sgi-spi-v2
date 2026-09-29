# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de cadastro e consulta de usuários.
"""Rotas de usuários (`/api/usuarios`).

Consultar exige ACL `usuarios` ≥ LEITURA; criar, alterar e excluir são exclusivos do SuperRoot.
As regras ficam em `servico_admin_usuarios`; aqui só se traduzem as exceções em respostas HTTP.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl, exigir_gestao
from app.core.erros import ErroApi
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, erro_regra, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.schemas.usuarios import AlteracaoUsuario, CriacaoUsuario, DetalheUsuario, OpcaoUsuario, PaginaUsuarios
from app.services import servico_admin_usuarios as servico
from app.services.servico_admin_usuarios import ErroRegraUsuario, UsuarioNaoEncontrado

roteador = APIRouter(prefix="/usuarios", tags=["Usuários"], responses=RESPOSTAS_AUTENTICADAS)

# Dependências de acesso reutilizadas nas rotas abaixo
pode_ler = exigir_acl("usuarios", NivelAcl.LEITURA)
pode_gerir = exigir_gestao("usuarios")


def _negar(detalhe: str) -> ErroApi:
    return ErroApi(status.HTTP_403_FORBIDDEN, detalhe, "acesso_negado")


def _restricoes_nao_superroot(autor: Usuario, *, alvo: Usuario | None = None, superusuario: bool | None = None,
                              senha: str | None = None) -> None:
    """Quem gere usuários pela ACL (ex.: a CGP) não pode tocar no que dá acesso de administrador:
    contas SuperRoot, o papel SuperRoot e senhas locais de outras pessoas (evita escalada de privilégio)."""
    if autor.superusuario:
        return
    if alvo is not None and alvo.superusuario:
        raise _negar("Somente um SuperRoot pode alterar ou excluir a conta de um administrador do sistema (SuperRoot).")
    if superusuario and (alvo is None or not alvo.superusuario):
        raise _negar("Somente um SuperRoot pode conceder o papel de administrador do sistema (SuperRoot).")
    if senha and alvo is not None:
        raise _negar("Somente um SuperRoot pode definir a senha local de outra pessoa.")
NAO_ENCONTRADO = resposta_nao_encontrado("Usuário")


@roteador.get(
    "",
    response_model=PaginaUsuarios,
    summary="Listar usuários",
    description="Pesquisa em login, nome, e-mail, ramal, celular, cargo, departamento e prédio. Exige ACL `usuarios` ≥ LEITURA.",
)
def listar_usuarios(
    busca: str | None = Query(None, max_length=100, description="Texto de pesquisa."),
    situacao: Literal["ativos", "inativos", "todos"] = Query("ativos", description="Situação da conta."),
    origem: Literal["local", "ldap", "local_ldap"] | None = Query(None, description="Origem da conta."),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(50, ge=1, le=200),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(pode_ler),
) -> PaginaUsuarios:
    """Lista paginada no servidor: o serviço devolve a página pedida e o total para a paginação da tela."""
    itens, total = servico.listar_usuarios(sessao, busca, situacao, origem, pagina, tamanho_pagina)
    return PaginaUsuarios(itens=itens, total=total, pagina=pagina, tamanho_pagina=tamanho_pagina)


@roteador.get(
    "/opcoes",
    response_model=list[OpcaoUsuario],
    summary="Opções de usuários para seletores",
    description="Forma reduzida (id, login, nome, cargo) para seletores de gestor, membros e regras. Exige ACL `usuarios` ≥ LEITURA.",
)
def listar_opcoes(
    busca: str | None = Query(None, max_length=100),
    limite: int = Query(20, ge=1, le=100),
    incluir_inativos: bool = Query(False),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(pode_ler),
) -> list[OpcaoUsuario]:
    """Busca rápida para campos de seleção (resposta curta, sem paginação)."""
    return servico.opcoes(sessao, busca, limite, incluir_inativos)


@roteador.get("/{usuario_id}", response_model=DetalheUsuario, summary="Consultar usuário", responses=NAO_ENCONTRADO)
def consultar_usuario(usuario_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> DetalheUsuario:
    """Detalhe de um usuário, com o perfil institucional."""
    try:
        return servico.para_detalhe(sessao, servico.obter_usuario(sessao, usuario_id))
    except UsuarioNaoEncontrado:
        raise nao_encontrado("Usuário")


@roteador.post(
    "",
    response_model=DetalheUsuario,
    status_code=status.HTTP_201_CREATED,
    summary="Criar conta local",
    description="Cria conta local com senha (hash bcrypt). SuperRoot, ou CONTROLE_TOTAL na ACL `usuarios` (sem conceder o papel SuperRoot).",
    responses={**CONFLITO, **INVALIDO},
)
def criar_usuario(dados: CriacaoUsuario, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_gerir)) -> DetalheUsuario:
    """Cria uma conta local (as contas do LDAP chegam pela sincronização, não por aqui)."""
    _restricoes_nao_superroot(autor, superusuario=dados.superusuario)
    try:
        return servico.para_detalhe(sessao, servico.criar_conta_local(sessao, dados, autor.login))
    except ErroRegraUsuario as erro:
        # Desfaz qualquer gravação parcial antes de responder o erro
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)


@roteador.put(
    "/{usuario_id}",
    response_model=DetalheUsuario,
    summary="Alterar usuário",
    description=(
        "Altera situação, papel SuperRoot, perfil institucional e, opcionalmente, a senha local. "
        "Definir senha numa conta `ldap` a torna `local_ldap`. SuperRoot, ou CONTROLE_TOTAL na ACL `usuarios`: neste caso sem "
        "mexer em contas SuperRoot, no papel SuperRoot nem na senha local (`403 acesso_negado`)."
    ),
    responses={**NAO_ENCONTRADO, **INVALIDO},
)
def alterar_usuario(
    usuario_id: int, dados: AlteracaoUsuario, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_gerir)
) -> DetalheUsuario:
    """Altera o usuário; o autor é repassado ao serviço para as regras que protegem a própria conta."""
    alvo = sessao.get(Usuario, usuario_id)
    if alvo is not None:
        _restricoes_nao_superroot(autor, alvo=alvo, superusuario=dados.superusuario, senha=dados.senha)
    try:
        return servico.para_detalhe(sessao, servico.alterar_usuario(sessao, usuario_id, dados, autor))
    except UsuarioNaoEncontrado:
        raise nao_encontrado("Usuário")
    except ErroRegraUsuario as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)


@roteador.delete(
    "/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir usuário",
    description="Exclui o usuário (exceto a conta administrativa principal e a própria conta). SuperRoot, ou CONTROLE_TOTAL na ACL "
                "`usuarios` (sem excluir contas SuperRoot).",
    responses={**NAO_ENCONTRADO, **INVALIDO},
)
def excluir_usuario(usuario_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_gerir)) -> Response:
    """Exclui o usuário e responde 204 (sem corpo)."""
    alvo = sessao.get(Usuario, usuario_id)
    if alvo is not None:
        _restricoes_nao_superroot(autor, alvo=alvo)
    try:
        servico.excluir_usuario(sessao, usuario_id, autor)
    except UsuarioNaoEncontrado:
        raise nao_encontrado("Usuário")
    except ErroRegraUsuario as erro:
        raise erro_regra(str(erro), erro.conflito)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
