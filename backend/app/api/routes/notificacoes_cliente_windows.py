# Criado por José Eduardo Santana Martins
# Este arquivo serve para manter as rotas que o cliente Windows (SGI Alertas) já instalado usa, no mesmo formato de sempre.
"""Compatibilidade com o cliente Windows (SGI Alertas), `/api/mensagens`.

O cliente instalado consulta `GET /api/mensagens/resumo` e `GET /api/mensagens?estado=pendentes…` a cada 60 segundos e lê só `id`, `assunto`,
`prioridade`, `categoria`, `autor_nome`, `link`, `itens`, `total`, `pendentes`, `nao_lidas` e `janela.id`. Estas duas rotas **ficam para sempre**,
no formato antigo, para ele não precisar de versão nova. A diferença: devolvem **só as entregas em que a pessoa ligou o canal Desktop**
(nas Preferências), então o cliente passa a respeitar a escolha de cada um. Os demais caminhos antigos foram substituídos por `/api/notificacoes`.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import RESPOSTAS_AUTENTICADAS
from app.api.routes.notificacoes import _detalhe, _resumo
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.notificacoes import EntregaResumo, PaginaEntregas, ResumoCaixa
from app.services import notificacoes as servico

roteador = APIRouter(prefix="/mensagens", tags=["Compatibilidade: cliente Windows"], responses=RESPOSTAS_AUTENTICADAS)


@roteador.get("/resumo", response_model=ResumoCaixa, summary="Resumo para o cliente Windows (só Desktop)",
              description="Mesmo formato de `GET /api/notificacoes/resumo`, mas conta só as entregas com o canal Desktop ligado. Rota mantida para o SGI Alertas já instalado.")
def resumo_desktop(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> ResumoCaixa:
    pendentes, nao_lidas, janela = servico.resumo(sessao, usuario, somente_desktop=True)
    return ResumoCaixa(pendentes=pendentes, nao_lidas=nao_lidas, janela=_detalhe(janela) if janela else None)


@roteador.get("", response_model=PaginaEntregas, summary="Caixa para o cliente Windows (só Desktop)",
              description="Mesmo formato de `GET /api/notificacoes`, mas só com as entregas em que o canal Desktop está ligado. Rota mantida para o SGI Alertas já instalado.")
def listar_desktop(estado: Literal["pendentes", "cientes", "todas"] = "pendentes", busca: str = Query("", max_length=200),
                   pagina: int = Query(1, ge=1), tamanho_pagina: int = Query(20, ge=1, le=100),
                   sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PaginaEntregas:
    itens, total = servico.listar(sessao, usuario, estado, busca, pagina, tamanho_pagina, somente_desktop=True)
    return PaginaEntregas(itens=[_resumo(e) for e in itens], total=total, pagina=pagina, tamanho_pagina=tamanho_pagina)
