# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a configuração da integração com o BookStack (exclusiva do SuperRoot).
"""Configuração da integração com o BookStack (`/api/integracao-bookstack`): endereço, token (cifrado), liga/desliga e teste."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis
from app.api.respostas import RESPOSTAS_AUTENTICADAS, VALIDACAO
from app.core.banco import obter_sessao
from app.models.usuario import Papel, Usuario
from app.services import servico_integracao_bookstack as servico
from app.services import servico_manuais
from app.services.servico_integracao_bookstack import AlteracaoIntegracaoBookstack, LeituraIntegracaoBookstack, ResultadoTesteBookstack

roteador = APIRouter(prefix="/integracao-bookstack", tags=["Integração BookStack"], responses=RESPOSTAS_AUTENTICADAS)
super_root = exigir_papeis(Papel.SUPER_ROOT)


@roteador.get("", response_model=LeituraIntegracaoBookstack, summary="Configuração da integração com o BookStack",
              description="Endereço, se está ligada e se há token gravado (o token nunca é devolvido). Restrito ao SuperRoot.")
def obter(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> LeituraIntegracaoBookstack:
    """Configuração atual, sem o token."""
    return servico.leitura(servico.obter(sessao))


@roteador.put("", response_model=LeituraIntegracaoBookstack, summary="Salvar a configuração da integração", responses=VALIDACAO,
              description="Grava endereço, liga/desliga e o token de API (cifrado no banco). `token_id` e `token_segredo` vazios preservam os atuais. "
              "Restrito ao SuperRoot.")
def salvar(dados: AlteracaoIntegracaoBookstack, sessao: Session = Depends(obter_sessao),
           autor: Usuario = Depends(super_root)) -> LeituraIntegracaoBookstack:
    """Salva a configuração e descarta o cache dos manuais."""
    config = servico.salvar(sessao, dados, autor.login)
    servico_manuais.limpar_cache()
    return servico.leitura(config)


@roteador.post("/testar", response_model=ResultadoTesteBookstack, summary="Testar a conexão com o BookStack",
               description="Lista os livros com a configuração gravada. Sempre responde 200: `sucesso` e `mensagem` dizem o resultado. Restrito ao SuperRoot.")
def testar(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> ResultadoTesteBookstack:
    """Teste de conexão."""
    return servico.testar(servico.obter(sessao), servico_manuais.TRANSPORTE)
