# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do painel e dos relatórios gerenciais de contratos.
"""Relatórios gerenciais da carteira (`/api/contratos/relatorios`), restritos ao SuperRoot,
e o painel de contratos (`/api/contratos/painel`), aberto a quem tem leitura no módulo.

Os relatórios são gerados em memória (PDF ou XLSX) e devolvidos como download.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis
from app.api.respostas import RESPOSTAS_AUTENTICADAS
from app.api.routes.contratos.comum import pode_ler
from app.core.banco import obter_sessao
from app.models.usuario import Papel, Usuario
from app.schemas.contratos.painel import Painel
from app.services.contratos import servico_orcamento, servico_painel, servico_relatorios

roteador = APIRouter(prefix="/contratos/relatorios", tags=["Contratos: relatórios"], responses=RESPOSTAS_AUTENTICADAS)
# O painel fica em outro roteador porque o prefixo é `/contratos`, não `/contratos/relatorios`
roteador_painel = APIRouter(prefix="/contratos", tags=["Contratos: painel"], responses=RESPOSTAS_AUTENTICADAS)
super_root = exigir_papeis(Papel.SUPER_ROOT)
# Documentação da resposta 200 de download (PDF ou planilha)
ARQUIVO = {status.HTTP_200_OK: {"content": {"application/pdf": {}, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
                                "description": "Arquivo PDF ou XLSX."}}


def _arquivo(conteudo: bytes, nome: str, tipo: str) -> Response:
    """Resposta de download: `Content-Disposition: attachment` faz o navegador salvar o arquivo."""
    return Response(conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@roteador.get("/notas-empenho", summary="Relatório Executivo de Notas de Empenho",
              description="Todas as NEs de todos os contratos, com valor inicial, consumido e saldo. Restrito ao SuperRoot.", responses=ARQUIVO)
def relatorio_notas(formato: Literal["xlsx", "pdf"] = Query("xlsx"), sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)):
    """Relatório de todas as NEs; o serviço devolve (conteúdo, nome do arquivo, tipo MIME)."""
    return _arquivo(*servico_orcamento.arquivo_relatorio_notas(sessao, formato, autor))


@roteador.get("/previsao-orcamentaria", summary="Exportar Previsão Orçamentária consolidada",
              description="Exercício, formato (PDF ou XLSX), seções (resumo anual e detalhamento mensal) e cenários em elaboração "
              "(reajustes, aditamentos, supressões e prorrogações) somados à previsão. Restrito ao SuperRoot.", responses=ARQUIVO)
def previsao_orcamentaria(
    exercicio: int = Query(..., ge=2000, le=2100),
    formato: Literal["xlsx", "pdf"] = Query("xlsx"),
    resumo_anual: bool = Query(True),
    detalhamento_mensal: bool = Query(True),
    cenario_reajustes: bool = Query(False),
    cenario_aditamentos: bool = Query(False),
    cenario_supressoes: bool = Query(False),
    cenario_prorrogacoes: bool = Query(False),
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(super_root),
):
    """Exporta a previsão consolidada do exercício, com as seções e os cenários escolhidos."""
    # Junta num conjunto só os nomes dos cenários marcados como verdadeiros
    cenarios = {nome for nome, ativo in (("reajustes", cenario_reajustes), ("aditamentos", cenario_aditamentos),
                                         ("supressoes", cenario_supressoes), ("prorrogacoes", cenario_prorrogacoes)) if ativo}
    return _arquivo(*servico_relatorios.exportar(sessao, exercicio, formato, resumo_anual, detalhamento_mensal, cenarios, autor))


@roteador_painel.get("/painel", response_model=Painel, summary="Painel de contratos",
                     description="Minhas pendências (contratos em que sou criador ou integrante da equipe), alertas de risco da carteira, "
                     "execução orçamentária do exercício (previsto × medido × pago) e números da carteira. Filtros opcionais por empresa "
                     "e contrato (não se aplicam às pendências). Exige ACL `contratos` ≥ LEITURA.")
def painel(
    exercicio: int | None = Query(None, ge=2000, le=2100),
    empresa_id: uuid.UUID | None = Query(None),
    contrato_id: uuid.UUID | None = Query(None),
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(pode_ler),
) -> Painel:
    """Monta todos os blocos do painel de uma vez; os cálculos ficam no serviço."""
    return servico_painel.montar_painel(sessao, usuario, exercicio, empresa_id, contrato_id)
