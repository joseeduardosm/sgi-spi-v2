# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de leitura e gravação dos parâmetros do módulo de contratos.
"""Parâmetros do módulo Contratos (`/api/contratos/parametros`): cortes de alertas, prazos, regras e limites."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS
from app.api.routes.contratos.comum import controle_total, pode_ler
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.contratos.parametros import GravacaoParametrosContratos, LeituraParametrosContratos
from app.services.contratos import servico_parametros

roteador = APIRouter(prefix="/contratos/parametros", tags=["Contratos: parâmetros"], responses=RESPOSTAS_AUTENTICADAS)


@roteador.get("", response_model=LeituraParametrosContratos, summary="Ler os parâmetros de Contratos",
              description="Valores atuais dos parâmetros do módulo (cortes de alertas, prazos, regras e limites), com quem alterou por último e os valores de fábrica em `padroes`. "
              "Exige ACL `contratos` ≥ LEITURA (as telas usam estes números em vez de repetir valores fixos).")
def ler_parametros(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Parâmetros atuais."""
    resposta = servico_parametros.leitura(sessao)
    sessao.commit()  # a primeira leitura num banco novo cria a linha com os padrões
    return resposta


@roteador.put("", response_model=LeituraParametrosContratos, summary="Gravar os parâmetros de Contratos", responses={**INVALIDO},
              description="Substitui o conjunto de parâmetros (envie todos). Só quem tem **controle total** em Contratos (ou SuperRoot): `403` para os demais. "
              "Valores fora dos limites ou incoerentes (ex.: prazo médio menor que o alto): `422`. Audita `contratos.parametros` com o antes e o depois de cada campo alterado.")
def gravar_parametros(dados: GravacaoParametrosContratos, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(controle_total)):
    """Grava os parâmetros."""
    return servico_parametros.salvar(sessao, dados, autor)
