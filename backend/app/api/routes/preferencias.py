# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as colunas que cada usuário escolheu mostrar nas listagens (por tela).
"""Preferências de colunas (`/api/preferencias/colunas/{tela}`): cada usuário lê e grava só as próprias."""

from typing import Annotated

from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import RESPOSTAS_AUTENTICADAS, VALIDACAO
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.preferencia_colunas import PreferenciaColunas
from app.models.usuario import Papel, Usuario
from app.schemas.preferencias import GravacaoColunas, PreferenciaColunasLeitura

roteador = APIRouter(prefix="/preferencias", tags=["Preferências de colunas"], responses=RESPOSTAS_AUTENTICADAS)

Tela = Annotated[str, Path(min_length=1, max_length=60, pattern=r"^[a-z0-9_.-]+$", description="Identificador da tela (ex.: `patrimonio.bens`).")]


Visao = Annotated[Literal["pessoal", "global"], Query(description="`pessoal` (padrão): a visão do próprio usuário. `global`: a visão de todos que não têm visão pessoal (só o SuperRoot grava).")]


def _preferencia(sessao: Session, usuario: Usuario | None, tela: str) -> PreferenciaColunas | None:
    """Visão pessoal do usuário; com `usuario=None`, a visão global da tela."""
    filtro = PreferenciaColunas.usuario_id == usuario.id if usuario is not None else PreferenciaColunas.usuario_id.is_(None)
    return sessao.scalar(select(PreferenciaColunas).where(filtro, PreferenciaColunas.tela == tela))


def _dono(sessao: Session, usuario: Usuario, visao: str) -> Usuario | None:
    """Quem é o dono da visão: o próprio usuário ou ninguém (global, que só o SuperRoot altera)."""
    if visao == "global":
        if not usuario.possui_papel(Papel.SUPER_ROOT):
            raise ErroApi(status.HTTP_403_FORBIDDEN, "Só o SuperRoot altera a visão global.", "acesso_negado")
        return None
    return usuario


def _leitura(sessao: Session, usuario: Usuario, tela: str) -> PreferenciaColunasLeitura:
    pessoal, global_ = _preferencia(sessao, usuario, tela), _preferencia(sessao, None, tela)
    return PreferenciaColunasLeitura(tela=tela, colunas=list(pessoal.colunas) if pessoal else None, padrao_global=list(global_.colunas) if global_ else None)


@roteador.get("/colunas/{tela}", response_model=PreferenciaColunasLeitura, summary="Minhas colunas da listagem",
              description="Colunas que o usuário escolheu mostrar na listagem da tela, na ordem (`colunas`; nulo = nunca escolheu), e a visão global da tela (`padrao_global`), usada por quem não tem visão pessoal. "
              "Cada usuário vê só as próprias.")
def minhas_colunas(tela: Tela, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PreferenciaColunasLeitura:
    """Lê a visão pessoal do usuário logado e a global da tela."""
    return _leitura(sessao, usuario, tela)


@roteador.put("/colunas/{tela}", response_model=PreferenciaColunasLeitura, summary="Salvar as colunas da listagem", responses={**VALIDACAO, 403: {"description": "`visao=global` sem ser SuperRoot (`acesso_negado`)."}},
              description="Substitui a lista inteira, na ordem enviada (de 1 a 80 ids, sem repetir), na visão pessoal (padrão) ou, com `visao=global`, na visão global (só SuperRoot). "
              "O servidor não confere se a tela conhece as colunas: a tela ignora as que não existirem mais.")
def salvar_colunas(tela: Tela, dados: GravacaoColunas, visao: Visao = "pessoal", sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PreferenciaColunasLeitura:
    """Grava (ou troca) as colunas da visão pessoal ou global."""
    dono = _dono(sessao, usuario, visao)
    linha = _preferencia(sessao, dono, tela)
    if linha is None:
        sessao.add(PreferenciaColunas(usuario_id=dono.id if dono else None, tela=tela, colunas=dados.colunas))
    else:
        linha.colunas = dados.colunas
    sessao.commit()
    return _leitura(sessao, usuario, tela)


@roteador.delete("/colunas/{tela}", status_code=status.HTTP_204_NO_CONTENT, summary="Restaurar o padrão das colunas", responses={403: {"description": "`visao=global` sem ser SuperRoot (`acesso_negado`)."}},
                 description="Apaga a visão pessoal (padrão) ou, com `visao=global`, a global (só SuperRoot): volta a valer a visão seguinte (global, depois o padrão da tela). Sem escolha anterior, também responde `204`.")
def restaurar_colunas(tela: Tela, visao: Visao = "pessoal", sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    """Remove a visão pessoal ou global."""
    linha = _preferencia(sessao, _dono(sessao, usuario, visao), tela)
    if linha is not None:
        sessao.delete(linha)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
