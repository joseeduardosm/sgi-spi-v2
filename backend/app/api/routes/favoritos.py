# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor os favoritos do menu (telas que o usuário fixou).
"""Favoritos do menu (`/api/favoritos`): cada usuário lê e grava só os próprios."""

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import RESPOSTAS_AUTENTICADAS, VALIDACAO
from app.core.banco import obter_sessao
from app.models.favorito_menu import FavoritoMenu
from app.models.usuario import Usuario
from app.schemas.favoritos import Favorito, GravacaoFavoritos, RespostaFavoritos

roteador = APIRouter(prefix="/favoritos", tags=["Favoritos do menu"], responses=RESPOSTAS_AUTENTICADAS)


def _lista(sessao: Session, usuario: Usuario) -> RespostaFavoritos:
    itens = sessao.scalars(select(FavoritoMenu).where(FavoritoMenu.usuario_id == usuario.id).order_by(FavoritoMenu.ordem, FavoritoMenu.id))
    return RespostaFavoritos(itens=[Favorito(rota=f.rota, rotulo=f.rotulo) for f in itens])


@roteador.get("", response_model=RespostaFavoritos, summary="Meus favoritos do menu",
              description="Telas que o usuário fixou, na ordem de exibição. Cada usuário vê só os próprios.")
def meus_favoritos(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> RespostaFavoritos:
    """Lista os favoritos do usuário logado."""
    return _lista(sessao, usuario)


@roteador.put("", response_model=RespostaFavoritos, summary="Salvar meus favoritos do menu", responses=VALIDACAO,
              description="Substitui a lista inteira, na ordem enviada. Máximo de 20; `rota` precisa ser interna (começar por `/`); rotas repetidas contam uma vez. "
              "Devolve a lista gravada.")
def salvar_favoritos(dados: GravacaoFavoritos, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> RespostaFavoritos:
    """Troca os favoritos do usuário pela lista enviada (sem repetir rotas)."""
    sessao.execute(delete(FavoritoMenu).where(FavoritoMenu.usuario_id == usuario.id))
    vistas: set[str] = set()
    for ordem, item in enumerate(dados.itens):
        if item.rota in vistas:
            continue
        vistas.add(item.rota)
        sessao.add(FavoritoMenu(usuario_id=usuario.id, rota=item.rota, rotulo=item.rotulo, ordem=ordem))
    sessao.commit()
    return _lista(sessao, usuario)
