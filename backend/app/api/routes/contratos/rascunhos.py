# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas dos rascunhos compartilhados dos formulários do contrato (diário, avaliação e medição).
"""Rascunhos salvos no servidor (`/api/contratos/{contrato_id}/rascunhos/{tipo}`).

Leitura: ACL `contratos` ≥ LEITURA (qualquer pessoa com acesso a Contratos vê o rascunho). Gravação e exclusão: quem pode editar o contrato
(equipe vigente, criador ou SuperRoot, com ACL ≥ MODIFICACAO). É adicional ao rascunho automático que o navegador guarda sozinho.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import SEM_VINCULO, pode_ler, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.contratos.rascunho import GravacaoRascunho, LeituraRascunho, TipoRascunho
from app.services.contratos import servico_rascunhos

roteador = APIRouter(prefix="/contratos/{contrato_id}/rascunhos", tags=["Contratos: rascunhos"], responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADO = resposta_nao_encontrado("Contrato, competência ou rascunho")


def _leitura(r, tipo: str, chave: str) -> LeituraRascunho:
    return LeituraRascunho(tipo=tipo, chave=r.chave, dados=r.dados, versao=r.versao, atualizado_em=r.atualizado_em,
                           atualizado_por_id=r.atualizado_por_id, atualizado_por_nome=r.atualizado_por_nome)


@roteador.get("/{tipo}", response_model=LeituraRascunho | None, summary="Ler o rascunho de uma tela",
              description="Rascunho salvo da tela (`diario`, `avaliacao` ou `medicao`) ou `null` se não há. Nas telas por competência, informe `chave` = id da competência.",
              responses=NAO_ENCONTRADO)
def ler(contrato_id: uuid.UUID, tipo: TipoRascunho, chave: str = Query("", max_length=60), sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    with traduzir_erros(sessao):
        r = servico_rascunhos.obter(sessao, contrato_id, tipo, chave)
        return _leitura(r, tipo, chave) if r else None


@roteador.put("/{tipo}", response_model=LeituraRascunho, summary="Salvar o rascunho de uma tela",
              description="Cria ou grava por cima o rascunho. Informe em `versao` a versão que você viu: se outra pessoa salvou depois, `409` (recarregue antes de salvar por cima). "
              "Só quem pode editar o contrato. O relato do diário é sanitizado como o da ocorrência.",
              responses={**NAO_ENCONTRADO, **INVALIDO, **CONFLITO, **SEM_VINCULO})
def salvar(contrato_id: uuid.UUID, tipo: TipoRascunho, dados: GravacaoRascunho, chave: str = Query("", max_length=60),
           sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        return _leitura(servico_rascunhos.gravar(sessao, contrato_id, tipo, chave, dados, autor), tipo, chave)


@roteador.delete("/{tipo}", status_code=status.HTTP_204_NO_CONTENT, summary="Apagar o rascunho de uma tela",
                 description="Apaga o rascunho salvo (quem pode editar o contrato). `404` se não há rascunho.", responses={**NAO_ENCONTRADO, **SEM_VINCULO})
def apagar(contrato_id: uuid.UUID, tipo: TipoRascunho, chave: str = Query("", max_length=60), sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_rascunhos.excluir(sessao, contrato_id, tipo, chave, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
