# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados do SLA (política de prazos e situação de cada item).
"""Schemas do SLA: política por módulo e prioridade, e a situação de cumprimento de uma tarefa ou sugestão."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

ModuloSla = Literal["tarefas", "melhorias"]
PrioridadeSla = Literal["", "baixa", "normal", "alta", "critica"]
SituacaoSla = Literal["no_prazo", "em_risco", "estourado", "cumprido", "cumprido_fora"]


class SlaItem(BaseModel):
    """Situação do SLA de um item (resposta e resolução, em dias úteis a partir do dia da criação)."""
    meta_resposta_dias: int = Field(..., description="Prazo de resposta (primeiro atendimento) em dias úteis.")
    meta_resolucao_dias: int = Field(..., description="Prazo de resolução em dias úteis.")
    prazo_resposta: date = Field(..., description="Último dia para responder (inclusive).")
    prazo_resolucao: date = Field(..., description="Último dia para resolver (inclusive).")
    respondido_em: datetime | None = None
    resolvido_em: datetime | None = None
    situacao_resposta: SituacaoSla = Field(..., description="`cumprido`/`cumprido_fora` se já respondeu; senão `no_prazo`, `em_risco` (80% do prazo consumido) ou `estourado`.")
    situacao_resolucao: SituacaoSla


class LeituraPoliticaSla(BaseModel):
    """Uma linha da política de SLA."""
    modulo: ModuloSla
    prioridade: PrioridadeSla = Field("", description="Vazia em Melhorias (regra única).")
    dias_uteis_resposta: int = Field(..., ge=0, le=365)
    dias_uteis_resolucao: int = Field(..., ge=0, le=365)
    ativo: bool = True


class GravacaoPoliticasSla(BaseModel):
    """Corpo do `PUT /sla/politicas`: a lista completa das linhas a gravar (as ausentes seguem como estão)."""
    politicas: list[LeituraPoliticaSla] = Field(..., min_length=1, max_length=20)
