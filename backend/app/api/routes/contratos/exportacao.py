# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor o download em XLSX do contrato, de um checklist e de um formulário de avaliação.
"""Exportação para XLSX (planilha já preenchida, no mesmo formato da importação).

- `GET /api/contratos/{contrato_id}/exportacao-xlsx`: o contrato (cabeçalho, equipe vigente e itens);
- `GET /api/contratos/{contrato_id}/checklists/{checklist_id}/xlsx`: uma versão do checklist;
- `GET /api/contratos/{contrato_id}/formularios/{formulario_id}/xlsx`: uma versão do formulário de avaliação.

Acesso: ACL `contratos` ≥ LEITURA (quem vê o contrato pode baixá-lo).
"""

import re
import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.respostas import RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import pode_ler, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.services.contratos import servico_configuracao_execucao as configuracao
from app.services.contratos import servico_exportacao_xlsx as exportacao
from app.services.contratos import servico_importacao_modelos_xlsx as modelos
from app.services.contratos.servico_contratos import obter_contrato

roteador = APIRouter(prefix="/contratos/{contrato_id}", tags=["Contratos: exportação para XLSX"], responses=RESPOSTAS_AUTENTICADAS)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
RESPOSTA_XLSX = {status.HTTP_200_OK: {"content": {XLSX: {}}, "description": "Planilha .xlsx para download."}}


def _resposta(conteudo: bytes, nome: str) -> Response:
    """Planilha como anexo; o nome perde o que não é letra ou dígito (o número do contrato tem barra)."""
    seguro = re.sub(r"[^0-9A-Za-z]+", "_", nome).strip("_") or "planilha"
    return Response(conteudo, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{seguro}.xlsx"'})


@roteador.get("/exportacao-xlsx", response_class=Response, summary="Baixar o contrato em XLSX",
              description="Planilha no formato da importação de contrato, preenchida com os dados cadastrados: número, empresa, preposto "
              "(o primeiro ativo da empresa), vigência, processos SEI, equipe vigente e itens financeiros. Exige ACL `contratos` ≥ LEITURA.",
              responses={**RESPOSTA_XLSX, **resposta_nao_encontrado("Contrato")})
def baixar_contrato(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> Response:
    """Contrato em planilha."""
    with traduzir_erros():
        contrato = obter_contrato(sessao, contrato_id)
        return _resposta(exportacao.gerar(contrato), f"contrato-{contrato.numero_arquivo}")


@roteador.get("/checklists/{checklist_id}/xlsx", response_class=Response, summary="Baixar uma versão do checklist em XLSX",
              description="Planilha no formato da importação de checklist, com os documentos da versão. Exige ACL `contratos` ≥ LEITURA.",
              responses={**RESPOSTA_XLSX, **resposta_nao_encontrado("Contrato ou checklist")})
def baixar_checklist(contrato_id: uuid.UUID, checklist_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> Response:
    """Versão do checklist em planilha."""
    with traduzir_erros():
        checklist = configuracao.obter_checklist(sessao, contrato_id, checklist_id)
        return _resposta(modelos.exportar_checklist(checklist), f"checklist-v{checklist.versao}-{checklist.nome}")


@roteador.get("/formularios/{formulario_id}/xlsx", response_class=Response, summary="Baixar uma versão do formulário de avaliação em XLSX",
              description="Planilha no formato da importação de formulário (abas Formulário, Escala, Faixas e Itens). Exige ACL `contratos` ≥ LEITURA.",
              responses={**RESPOSTA_XLSX, **resposta_nao_encontrado("Contrato ou formulário")})
def baixar_formulario(contrato_id: uuid.UUID, formulario_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> Response:
    """Versão do formulário em planilha."""
    with traduzir_erros():
        formulario = configuracao.obter_formulario(sessao, contrato_id, formulario_id)
        return _resposta(modelos.exportar_formulario(formulario), f"formulario-v{formulario.versao}-{formulario.nome}")
