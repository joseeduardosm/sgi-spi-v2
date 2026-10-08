# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato da verificação de autenticidade dos PDFs gerados pelo sistema.
"""Schemas da verificação de documentos (`/api/contratos/verificar-documento`)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CienciaRegistrada(BaseModel):
    nome: str
    papel: str
    em: str


class DocumentoVerificado(BaseModel):
    """Dados do registro de autenticação de um PDF gerado pelo sistema."""
    tipo: str
    contrato_id: uuid.UUID
    contrato_numero: str
    competencia: str | None = None
    gerado_por: str
    gerado_em: datetime
    codigo: str = Field(..., description="Código de verificação impresso na Folha de autenticação.")
    sha256: str = Field(..., description="SHA-256 do arquivo completo (com a Folha de autenticação).")
    ciencias: list[CienciaRegistrada] = Field(default_factory=list, description="Quem tinha dado ciência quando o documento foi gerado.")


class VerificacaoDocumento(BaseModel):
    """Resultado da verificação por código ou por arquivo."""
    valido: bool
    motivo: str
    documento: DocumentoVerificado | None = None
