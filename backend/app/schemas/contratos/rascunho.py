# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os schemas dos rascunhos compartilhados dos formulários do contrato.
"""Schemas do rascunho salvo no servidor (`/api/contratos/{id}/rascunhos/{tipo}`)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TipoRascunho = Literal["diario", "avaliacao", "medicao"]


class GravacaoRascunho(BaseModel):
    """Campos do formulário a guardar."""
    dados: dict[str, Any] = Field(..., description="Campos do formulário (texto e números; arquivos não entram). Até 300 000 caracteres em JSON.")
    versao: int | None = Field(None, description="Versão do rascunho que a pessoa viu (`null`/0 se não havia). Se outra pessoa salvou depois, a gravação é recusada (`409`).")


class LeituraRascunho(BaseModel):
    """Rascunho salvo, com quem e quando o guardou."""
    tipo: TipoRascunho
    chave: str = Field(..., description="Id da competência (avaliação e medição); vazio no diário.")
    dados: dict[str, Any]
    versao: int = Field(..., description="Sobe a cada gravação; informe-a ao gravar por cima.")
    atualizado_em: datetime
    atualizado_por_id: int | None
    atualizado_por_nome: str
