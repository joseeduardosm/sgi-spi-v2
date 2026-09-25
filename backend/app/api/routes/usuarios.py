# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de cadastro e consulta de usuários.

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl, exigir_papeis
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, erro_regra, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.models.acl import NivelAcl
from app.models.usuario import Papel, Usuario
from app.schemas.usuarios import AlteracaoUsuario, CriacaoUsuario, DetalheUsuario, OpcaoUsuario, PaginaUsuarios
from app.services import servico_admin_usuarios as servico
from app.services.servico_admin_usuarios import ErroRegraUsuario, UsuarioNaoEncontrado

roteador = APIRouter(prefix="/usuarios", tags=["Usuários"], responses=RESPOSTAS_AUTENTICADAS)

pode_ler = exigir_acl("usuarios", NivelAcl.LEITURA)
super_root = exigir_papeis(Papel.SUPER_ROOT)
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
    return servico.opcoes(sessao, busca, limite, incluir_inativos)


@roteador.get("/{usuario_id}", response_model=DetalheUsuario, summary="Consultar usuário", responses=NAO_ENCONTRADO)
def consultar_usuario(usuario_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> DetalheUsuario:
    try:
        return servico.para_detalhe(sessao, servico.obter_usuario(sessao, usuario_id))
    except UsuarioNaoEncontrado:
        raise nao_encontrado("Usuário")


@roteador.post(
    "",
    response_model=DetalheUsuario,
    status_code=status.HTTP_201_CREATED,
    summary="Criar conta local",
    description="Cria conta local com senha (hash bcrypt). Restrito ao SuperRoot.",
    responses={**CONFLITO, **INVALIDO},
)
def criar_usuario(dados: CriacaoUsuario, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> DetalheUsuario:
    try:
        return servico.para_detalhe(sessao, servico.criar_conta_local(sessao, dados, autor.login))
    except ErroRegraUsuario as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)


@roteador.put(
    "/{usuario_id}",
    response_model=DetalheUsuario,
    summary="Alterar usuário",
    description=(
        "Altera situação, papel SuperRoot, perfil institucional e, opcionalmente, a senha local. "
        "Definir senha numa conta `ldap` a torna `local_ldap`. Restrito ao SuperRoot."
    ),
    responses={**NAO_ENCONTRADO, **INVALIDO},
)
def alterar_usuario(
    usuario_id: int, dados: AlteracaoUsuario, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)
) -> DetalheUsuario:
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
    description="Exclui o usuário (exceto a conta administrativa principal e a própria conta). Restrito ao SuperRoot.",
    responses={**NAO_ENCONTRADO, **INVALIDO},
)
def excluir_usuario(usuario_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> Response:
    try:
        servico.excluir_usuario(sessao, usuario_id, autor)
    except UsuarioNaoEncontrado:
        raise nao_encontrado("Usuário")
    except ErroRegraUsuario as erro:
        raise erro_regra(str(erro), erro.conflito)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
