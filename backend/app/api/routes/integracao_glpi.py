# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a configuração da integração com o GLPI (exclusiva do SuperRoot).
"""Configuração da integração com o GLPI (`/api/integracao-glpi`): endereço, tokens (cifrados), liga/desliga e teste de conexão."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis
from app.api.respostas import RESPOSTAS_AUTENTICADAS, VALIDACAO
from app.core.banco import obter_sessao
from app.models.usuario import Papel, Usuario
from app.services import servico_integracao_glpi as servico
from app.services.servico_integracao_glpi import AlteracaoIntegracaoGlpi, LeituraIntegracaoGlpi, ResultadoTesteGlpi

roteador = APIRouter(prefix="/integracao-glpi", tags=["Integração GLPI"], responses=RESPOSTAS_AUTENTICADAS)
super_root = exigir_papeis(Papel.SUPER_ROOT)


@roteador.get("", response_model=LeituraIntegracaoGlpi, summary="Configuração da integração com o GLPI",
              description="Endereço, se está ligada e se há tokens gravados (os tokens nunca são devolvidos). Restrito ao SuperRoot.")
def obter(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> LeituraIntegracaoGlpi:
    """Configuração atual, sem os tokens."""
    return servico.leitura(servico.obter(sessao))


@roteador.put("", response_model=LeituraIntegracaoGlpi, summary="Salvar a configuração da integração", responses=VALIDACAO,
              description="Grava endereço, liga/desliga e os tokens (cifrados no banco). `app_token` e `user_token` vazios preservam os atuais. Restrito ao SuperRoot.")
def salvar(dados: AlteracaoIntegracaoGlpi, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> LeituraIntegracaoGlpi:
    """Salva a configuração."""
    return servico.leitura(servico.salvar(sessao, dados, autor.login))


@roteador.post("/testar", response_model=ResultadoTesteGlpi, summary="Testar a conexão com o GLPI",
               description="Abre e encerra uma sessão na API do GLPI com a configuração gravada. Sempre responde 200: `sucesso` e `mensagem` dizem o resultado. Restrito ao SuperRoot.")
def testar(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> ResultadoTesteGlpi:
    """Teste de conexão."""
    return servico.testar(servico.obter(sessao))
