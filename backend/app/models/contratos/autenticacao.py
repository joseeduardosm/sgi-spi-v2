# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar o registro dos PDFs autenticados pelo sistema (código de verificação, hash e quem deu ciência).
"""Documentos autenticados: cada PDF gerado pelo sistema que recebe a "Folha de autenticação" é registrado aqui, para a conferência posterior."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson


class DocumentoAutenticado(Base):
    """Registro de um PDF com Folha de autenticação.

    `codigo` é o código de verificação impresso na folha (início do SHA-256 do conteúdo, sem a folha); `sha256_final` é o hash do arquivo completo,
    usado para conferir um PDF enviado para verificação. `ciencias` guarda o retrato de quem deu ciência quando o documento foi gerado.
    """
    __tablename__ = "contratos_documentos_autenticados"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(32), index=True)
    sha256_conteudo: Mapped[str] = mapped_column(String(64))
    sha256_final: Mapped[str] = mapped_column(String(64), index=True)
    tipo: Mapped[str] = mapped_column(String(60))
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    competencia_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="SET NULL"))
    anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="SET NULL"))
    gerado_por_nome: Mapped[str] = mapped_column(String(200), default="")
    gerado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    ciencias: Mapped[list[dict[str, Any]]] = mapped_column(TipoJson, default=list)
