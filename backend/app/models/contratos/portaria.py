# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar as autoridades signatárias e as portarias de designação de gestão e fiscalização dos contratos.
"""Portarias contratuais: autoridades que assinam e a portaria de cada contrato (número reservado no Protocolo, aceite e PDF publicado)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.anexo import Anexo
from app.models.auditoria import TipoJson

# Situações da portaria: nomeação (dados do RH pendentes) → aguardando ciência dos nomeados → aguardando autoridade (todos cientes; falta escolher
# a autoridade, quando o número é reservado) → aguardando aceite da autoridade → aceita → publicada (o Protocolo anexou o PDF do D.O.E.); ou cancelada
STATUS_PORTARIA = ("nomeacao", "aguardando_ciencia", "aguardando_autoridade", "aguardando_aceite", "aceita", "publicada", "cancelada")


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
    # Sigla, número e exercício só existem depois que a autoridade é escolhida (aí o número é reservado no Protocolo)
    sigla: Mapped[str] = mapped_column(String(60), default="")
    numero: Mapped[int | None] = mapped_column(Integer)
    exercicio: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="nomeacao", index=True)
    evidencia_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="SET NULL"))
    evidencia: Mapped[Anexo | None] = relationship(foreign_keys=[evidencia_anexo_id])
    nomeacoes: Mapped[list["NomeacaoPortaria"]] = relationship(back_populates="portaria", cascade="all, delete-orphan", order_by="NomeacaoPortaria.ordem")
    portaria_anterior_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_portarias.id", ondelete="SET NULL"))
    dados: Mapped[dict[str, Any]] = mapped_column(TipoJson, default=dict)
    motivo: Mapped[str] = mapped_column(Text, default="")
    solicitada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    solicitada_por_nome: Mapped[str] = mapped_column(String(200), default="")
    solicitada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    aceita_por_nome: Mapped[str | None] = mapped_column(String(200))
    aceita_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NomeacaoPortaria(Base):
    """Uma nomeação da portaria (função + usuário), com a ciência do nomeado. No máximo uma por função em cada portaria."""
    __tablename__ = "contratos_portarias_nomeacoes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portaria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_portarias.id", ondelete="CASCADE"), index=True)
    papel: Mapped[str] = mapped_column(String(40))
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    nome_usuario: Mapped[str] = mapped_column(String(200))
    ciente_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    portaria: Mapped["PortariaContrato"] = relationship(back_populates="nomeacoes")
