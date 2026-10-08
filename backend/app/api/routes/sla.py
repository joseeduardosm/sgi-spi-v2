# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a política de SLA (leitura para quem gerencia e gravação por ACL).
"""Política de SLA (`/api/sla/politicas`): prazos de resposta e de resolução em dias úteis, por módulo e prioridade.

Ler e gravar exige o recurso de ACL `sla`: leitura ≥ LEITURA, gravação ≥ MODIFICACAO (o recurso nasce fechado, só para a conta administrativa)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl
from app.api.respostas import RESPOSTAS_AUTENTICADAS, VALIDACAO
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.schemas.sla import GravacaoPoliticasSla, LeituraPoliticaSla
from app.services.servico_auditoria import auditar
from app.services.sla import servico_sla
from app.services.sla.erros import ErroSla

roteador = APIRouter(prefix="/sla", tags=["SLA"], responses=RESPOSTAS_AUTENTICADAS)
pode_ler = exigir_acl("sla", NivelAcl.LEITURA)
pode_gravar = exigir_acl("sla", NivelAcl.MODIFICACAO)


@roteador.get("/politicas", response_model=list[LeituraPoliticaSla], summary="Política de SLA",
              description="Prazos de resposta e de resolução, em dias úteis, de Tarefas (por prioridade) e de Melhorias (regra única). Linhas ainda não gravadas "
                          "aparecem com o prazo padrão. Exige ACL `sla` ≥ LEITURA.")
def listar(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> list[LeituraPoliticaSla]:
    """Linhas da política para a tela de administração."""
    return servico_sla.listar_politicas(sessao)


@roteador.put("/politicas", response_model=list[LeituraPoliticaSla], summary="Gravar a política de SLA",
              description="Grava as linhas informadas. A resolução não pode ser menor que a resposta (`400`) e só valem as combinações existentes: tarefas "
                          "(`baixa`, `normal`, `alta`, `critica`) e melhorias (prioridade vazia). Linha com `ativo=false` volta ao prazo padrão. Exige ACL `sla` ≥ MODIFICACAO.",
              responses={**VALIDACAO})
def gravar(dados: GravacaoPoliticasSla, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_gravar)) -> list[LeituraPoliticaSla]:
    """Atualiza a política e registra a auditoria."""
    try:
        linhas = servico_sla.gravar_politicas(sessao, dados)
    except ErroSla as erro:
        sessao.rollback()
        raise ErroApi(400, str(erro), "regra_negocio") from erro
    auditar(sessao, autor.login, "sla.politicas.gravar", "Política de SLA", autor_id=autor.id, alvo_tipo="sla", dados={"linhas": [l.model_dump() for l in dados.politicas]})
    sessao.commit()
    return linhas
