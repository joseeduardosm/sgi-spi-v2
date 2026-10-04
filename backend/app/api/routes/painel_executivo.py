# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do Painel Executivo (slides de contratos, RH e tarefas, PDF e verificação de acesso).
"""Rotas `/api/painel-executivo`: visão da organização inteira para a Diretoria.

Acesso: SuperRoot ou quem recebeu regra no recurso ACL `painel-executivo`. **Sem nenhuma regra, só o SuperRoot acessa.**
Os números têm cache de 60 segundos por processo.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import RESPOSTAS_AUTENTICADAS
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.painel_executivo import AcessoPainel, SlideContratos, SlideRh, SlideTarefas
from app.services.painel_executivo import acesso, cache, pdf, slides

roteador = APIRouter(prefix="/painel-executivo", tags=["Painel Executivo"], responses=RESPOSTAS_AUTENTICADAS)
ACL_NEGADA = {status.HTTP_403_FORBIDDEN: {"description": "Sem acesso ao recurso `painel-executivo` (`acl_negado`)."}}


def _autorizado(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Usuario:
    acesso.exigir(sessao, usuario)
    return usuario


@roteador.get("/acesso", response_model=AcessoPainel, summary="Posso ver o Painel Executivo?")
def ver_acesso(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> AcessoPainel:
    """Usado pelo portal para decidir se mostra o painel na página inicial e o item da barra lateral. Nunca devolve 403."""
    return AcessoPainel(pode=acesso.pode_ver(sessao, usuario))


def _contratos(sessao: Session, exercicio: int | None) -> SlideContratos:
    return cache.obter(("contratos", exercicio), lambda: slides.contratos(sessao, exercicio))


def _rh(sessao: Session, ano: int | None) -> SlideRh:
    return cache.obter(("rh", ano), lambda: slides.rh(sessao, ano))


def _tarefas(sessao: Session) -> SlideTarefas:
    return cache.obter(("tarefas",), lambda: slides.tarefas(sessao))


@roteador.get("/contratos", response_model=SlideContratos, summary="Slide de contratos", responses=ACL_NEGADA)
def slide_contratos(exercicio: int | None = Query(None, ge=2000, le=2100, description="Padrão: ano corrente."),
                    sessao: Session = Depends(obter_sessao), _: Usuario = Depends(_autorizado)) -> SlideContratos:
    """Carteira, execução (previsto × medido × pago, mensal e acumulada), vencimentos em 30/60/90 dias e os 5 contratos de maior risco."""
    return _contratos(sessao, exercicio)


@roteador.get("/rh", response_model=SlideRh, summary="Slide de RH", responses=ACL_NEGADA)
def slide_rh(ano: int | None = Query(None, ge=2000, le=2100, description="Padrão: ano corrente."),
             sessao: Session = Depends(obter_sessao), _: Usuario = Depends(_autorizado)) -> SlideRh:
    """Quem está de férias ou licença hoje, afastados por mês e por setor, férias a vencer e setores acima do limite. Visão global (sem escopo por papel)."""
    return _rh(sessao, ano)


@roteador.get("/tarefas", response_model=SlideTarefas, summary="Slide de tarefas", responses=ACL_NEGADA)
def slide_tarefas(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(_autorizado)) -> SlideTarefas:
    """Totais da organização, situação por equipe e tarefas criadas × concluídas nas últimas 12 semanas."""
    return _tarefas(sessao)


@roteador.get("/{slide}/pdf", summary="Baixar o slide em PDF", responses={**ACL_NEGADA, 200: {"content": {"application/pdf": {}}, "description": "PDF do slide."}})
def slide_pdf(slide: Literal["contratos", "rh", "tarefas"], sessao: Session = Depends(obter_sessao), _: Usuario = Depends(_autorizado)) -> Response:
    """PDF em paisagem com os mesmos números do slide e gráficos desenhados no servidor."""
    conteudo = {"contratos": lambda: pdf.contratos(_contratos(sessao, None)), "rh": lambda: pdf.rh(_rh(sessao, None)),
                "tarefas": lambda: pdf.tarefas(_tarefas(sessao))}[slide]()
    return Response(conteudo, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="painel-executivo-{slide}.pdf"'})
