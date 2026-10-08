# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados do calendário de vencimentos de contratos.
"""Schemas do calendário de vencimentos (`GET /api/contratos/calendario`)."""

import uuid
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.contratos.tipos import ValorMonetario

TipoEventoCalendario = Literal[
    "vigencia_fim", "vigencia_maxima", "reajuste", "pagamento_nf", "prazo_nf_48h", "validade_documento", "medicao_atrasada", "empenho_insuficiente",
    "tarefa_contrato",
]
SeveridadeEvento = Literal["alta", "media", "info"]


class EventoCalendario(BaseModel):
    """Um vencimento ou prazo de um contrato numa data."""
    data: date
    hora: time | None = Field(None, description="Hora do prazo, quando faz sentido (prazo de 48 h da NF e prazo das tarefas), no horário de São Paulo.")
    tipo: TipoEventoCalendario
    contrato_id: uuid.UUID
    contrato_numero: str
    contrato_apelido: str
    rotulo: str
    rota: str = Field(..., description="Caminho da tela no Angular onde o assunto é tratado.")
    severidade: SeveridadeEvento = Field(..., description="`alta` (vencido ou até 30 dias), `media` (31 a 60 dias, ou perto) ou `info`.")
    competencia_id: uuid.UUID | None = None
    valor: ValorMonetario | None = None


class Calendario(BaseModel):
    """Eventos do período pedido, em ordem de data."""
    de: date
    ate: date
    eventos: list[EventoCalendario]
