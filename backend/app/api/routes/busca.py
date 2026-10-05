# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a busca global do portal (uma consulta em vários módulos).
"""Busca global (`GET /api/busca`): procura ao mesmo tempo em contratos, contratações, tarefas, pessoas e setores."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import RESPOSTAS_AUTENTICADAS
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.busca import RespostaBusca
from app.services import servico_busca

roteador = APIRouter(prefix="/busca", tags=["Busca global"], responses=RESPOSTAS_AUTENTICADAS)


@roteador.get(
    "",
    response_model=RespostaBusca,
    summary="Busca global",
    description="Procura `q` (mínimo 2 caracteres) em contratos (número, apelido, empresa, objeto), contratações (nome, processo), tarefas do próprio usuário "
    "(título ou número), pessoas (diretório de ramais) e setores, com até 5 resultados por módulo. Cada módulo só aparece se o usuário tem "
    "pelo menos LEITURA no recurso de ACL dele (`contratos`, `contratacoes`, `setores`); pessoas valem para todo usuário logado. "
    "Sem `q` ou com menos de 2 caracteres, devolve lista vazia.",
)
def buscar(q: str = Query("", max_length=100), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> RespostaBusca:
    """Resultados agrupáveis por `tipo`, já com a rota de destino."""
    return RespostaBusca(itens=servico_busca.buscar(sessao, usuario, q))
