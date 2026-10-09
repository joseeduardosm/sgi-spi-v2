# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas dos modelos globais de checklist e de formulário.
"""Modelos globais de checklist, de formulário e máscaras de portaria (`/api/contratos/modelos`).

Um modelo global é um "molde" mantido pelo SuperRoot. Na aba Checklists ou Formulários de um
contrato, o usuário escolhe um modelo e o sistema faz uma cópia independente dentro do contrato;
alterar ou excluir o modelo depois não afeta as cópias já feitas.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import pode_ler, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.contratos.execucao import GravacaoModelo, LeituraModelo, PlaceholderPortaria
from app.services.contratos import portaria_mascara, servico_configuracao_execucao as servico

roteador = APIRouter(prefix="/contratos/modelos", tags=["Contratos: modelos globais"], responses=RESPOSTAS_AUTENTICADAS)
# Criar, alterar e excluir: checklists e formulários só o SuperRoot; máscaras de portaria também quem tem controle total em Contratos
# (a regra por tipo fica no serviço); listar basta ter leitura em contratos
NAO_ENCONTRADO = resposta_nao_encontrado("Modelo")


@roteador.get("", response_model=list[LeituraModelo], summary="Listar modelos globais",
              description="Modelos de checklist e de formulário para clonar nos contratos e máscaras de portaria. Exige ACL `contratos` ≥ LEITURA.")
def listar_modelos(
    tipo: Literal["checklist", "formulario", "portaria"] | None = Query(None),
    somente_ativos: bool = Query(True),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(pode_ler),
):
    """Lista os modelos, opcionalmente filtrando pelo tipo e escondendo os inativos."""
    return servico.listar_modelos(sessao, tipo, somente_ativos)


@roteador.get("/portaria/placeholders", response_model=list[PlaceholderPortaria], summary="Placeholders da máscara de portaria",
              description="Lista fechada de placeholders aceitos nas máscaras de portaria, com a descrição de cada um. Exige ACL `contratos` ≥ LEITURA.")
def listar_placeholders(_: Usuario = Depends(pode_ler)):
    """Placeholders permitidos (os da portaria anterior só valem na máscara com portaria anterior)."""
    return [PlaceholderPortaria(nome=nome, descricao=descricao, da_anterior=nome in portaria_mascara.DA_ANTERIOR) for nome, descricao in portaria_mascara.PLACEHOLDERS.items()]


@roteador.post("", response_model=LeituraModelo, status_code=status.HTTP_201_CREATED, summary="Criar modelo global",
               description="Checklist e formulário: só SuperRoot. Portaria: SuperRoot ou controle total em Contratos (`403` para os demais). Placeholders fora da lista, ou duas máscaras ativas da mesma variante, são recusados (`400`/`409`).", responses=INVALIDO)
def criar_modelo(dados: GravacaoModelo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_ler)):
    """Cria um modelo; `traduzir_erros` converte regras violadas em 400."""
    with traduzir_erros(sessao):
        return servico.leitura_modelo(servico.salvar_modelo(sessao, dados, autor))


@roteador.put("/{modelo_id}", response_model=LeituraModelo, summary="Alterar modelo global",
              description="O tipo não muda. Mesmas permissões e regras da criação.", responses={**NAO_ENCONTRADO, **INVALIDO})
def alterar_modelo(modelo_id: uuid.UUID, dados: GravacaoModelo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_ler)):
    """Altera o modelo (o conteúdo enviado substitui o anterior)."""
    with traduzir_erros(sessao):
        return servico.leitura_modelo(servico.salvar_modelo(sessao, dados, autor, modelo_id))


@roteador.delete("/{modelo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir modelo global",
                 description="As cópias já feitas nos contratos não mudam. Mesmas permissões da criação.", responses=NAO_ENCONTRADO)
def excluir_modelo(modelo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_ler)) -> Response:
    """Exclui o modelo; as cópias nos contratos continuam intactas."""
    with traduzir_erros(sessao):
        servico.excluir_modelo(sessao, modelo_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
