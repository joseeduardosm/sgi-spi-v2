"""
===============================================================================
ARQUIVO: eventos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Formato da resposta da aba "Eventos" do contrato: a lista do que aconteceu
nele (lida da auditoria), com categoria, quem fez e, nos eventos que podem ser
desfeitos, o estado do botão "Tornar sem efeito".

RESUMO TÉCNICO:
Modelos Pydantic de leitura: `EventoContrato` (uma linha) e
`PaginaEventosContrato` (página, total e contagem por categoria).

FINALIDADE DE NEGÓCIO:
Dá a quem tem Controle total em Contratos a visão completa e auditável da
história do contrato.

CONTEXTO NO SISTEMA:
Usado pela rota GET /contratos/{id}/eventos (api/routes/contratos/contratos.py)
e montado por app/services/contratos/servico_eventos.py.

===============================================================================
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CategoriaEvento = Literal["altera_contrato", "execucao", "documentos", "equipe_cadastro", "sem_efeito"]


class EventoContrato(BaseModel):
    """Uma linha da aba Eventos."""
    id: int = Field(..., description="Número do registro de auditoria.")
    ocorrido_em: datetime
    acao: str = Field(..., description="Ação técnica (ex.: `contrato.reajuste.concluir`).")
    evento: str = Field(..., description="Nome em linguagem de usuário (ex.: \"Reajuste concluído\").")
    categoria: CategoriaEvento
    autor: str = Field(..., description="Nome de quem fez (ou o login, se o usuário não existe mais).")
    detalhe: str = Field("", description="Resumo do que mudou (motivo, de/para ou a descrição gravada).")
    registro_tipo: Literal["reajustes", "repactuacoes", "alteracoes", "prorrogacoes", "vigencias-retroativas"] | None = Field(
        None, description="Nos eventos de conclusão: o tipo do registro, para `POST …/{registro_tipo}/{registro_id}/sem-efeito`.")
    registro_id: uuid.UUID | None = Field(None, description="Nos eventos de conclusão: o registro que pode ser tornado sem efeito.")
    sem_efeito: bool = Field(False, description="O registro desta conclusão já foi tornado sem efeito.")
    pode_tornar_sem_efeito: bool = False
    motivo_bloqueio: str = Field("", description="Por que o botão fica desativado (vazio se pode ou se o evento não tem botão).")


class PaginaEventosContrato(BaseModel):
    """Página da aba Eventos."""
    itens: list[EventoContrato]
    total: int = Field(..., description="Total de eventos com o filtro e a busca atuais.")
    pagina: int
    por_pagina: int
    por_categoria: dict[str, int] = Field(default_factory=dict, description="Quantos eventos há em cada categoria, com a busca atual (para os chips).")
