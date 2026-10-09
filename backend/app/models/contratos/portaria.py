# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar as autoridades signatárias e as portarias de designação de gestão e fiscalização dos contratos.
"""Portarias contratuais: autoridades que assinam e a portaria de cada contrato (número reservado no Protocolo, aceite e PDF publicado)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson

# Situações da portaria: aguardando o aceite da autoridade → aceita → publicada (PDF publicado anexado); devolvida volta ao solicitante
STATUS_PORTARIA = ("aguardando_aceite", "devolvida", "aceita", "publicada", "cancelada")


class AutoridadePortaria(Base):
    """Autoridade que assina as portarias (administrada por quem tem controle total em Contratos).

    `sigla` compõe o título ("Portaria SPI SSGC nº 015, de 2026"); `usuario_id` é quem dá o aceite pela autoridade.
    """
    __tablename__ = "portarias_autoridades"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sigla: Mapped[str] = mapped_column(String(60))
    nome: Mapped[str] = mapped_column(String(200))
    cargo: Mapped[str] = mapped_column(String(200))
    setor: Mapped[str] = mapped_column(String(200))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class PortariaContrato(Base):
    """Portaria de designação de um contrato. `dados` congela o retrato usado no texto (equipe, RS, autoridade, objeto, Art. 5º)."""
    __tablename__ = "contratos_portarias"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    autoridade_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("portarias_autoridades.id", ondelete="SET NULL"))
    numero_protocolo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("protocolo_numeros.id", ondelete="SET NULL"), index=True)
    sigla: Mapped[str] = mapped_column(String(60))
    numero: Mapped[int] = mapped_column(Integer)
    exercicio: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="aguardando_aceite", index=True)
    portaria_anterior_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_portarias.id", ondelete="SET NULL"))
    dados: Mapped[dict[str, Any]] = mapped_column(TipoJson, default=dict)
    motivo: Mapped[str] = mapped_column(Text, default="")
    solicitada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    solicitada_por_nome: Mapped[str] = mapped_column(String(200), default="")
    solicitada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    aceita_por_nome: Mapped[str | None] = mapped_column(String(200))
    aceita_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
