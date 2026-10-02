# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do Protocolo (numeração institucional de ofícios, portarias, resoluções etc.).
"""Módulo Protocolo.

- `TipoProtocolo`: tipo de documento (Ofício, Portaria…), cadastrado pela administração (CONTROLE_TOTAL).
- `SequenciaProtocolo`: faixa de números de um tipo **em um exercício** (a numeração reinicia a cada ano: "005/2026").
  A administração pode ampliá-la para trás e para frente.
- `NumeroProtocolo`: cada posição da faixa, materializada em linha para a reserva ser atômica e para a grade da tela.
  Estado derivado: livre, reservado, utilizado (tem documento) ou anulado.
- `EventoProtocolo`: linha do tempo do número (reservou, anexou, liberou, anulou…), que sobrevive a liberações.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.anexo import Anexo
from app.models.auditoria import TipoJson

TIPOS_EVENTO = ("reservou", "lancou", "anexou", "liberou", "anulou", "sigilo", "vinculou", "ampliou")


class TipoProtocolo(Base):
    """Tipo de documento numerado."""
    __tablename__ = "protocolo_tipos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(200))
    # Nome em minúsculas (sem diferenciar maiúsculas) para garantir a unicidade no banco
    nome_chave: Mapped[str] = mapped_column(String(200), unique=True)
    # Origem no SGI SPI antigo (recarga idempotente da migração)
    origem_sgi_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    sequencias: Mapped[list["SequenciaProtocolo"]] = relationship(back_populates="tipo", order_by="SequenciaProtocolo.exercicio.desc()")


class SequenciaProtocolo(Base):
    """Faixa de números de um tipo em um exercício (ano)."""
    __tablename__ = "protocolo_sequencias"
    __table_args__ = (UniqueConstraint("tipo_id", "exercicio", name="uq_protocolo_sequencias_tipo_exercicio"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tipo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("protocolo_tipos.id", ondelete="CASCADE"), index=True)
    exercicio: Mapped[int] = mapped_column(Integer)
    inicio: Mapped[int] = mapped_column(Integer)
    fim: Mapped[int] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    tipo: Mapped[TipoProtocolo] = relationship(back_populates="sequencias")
    numeros: Mapped[list["NumeroProtocolo"]] = relationship(back_populates="sequencia", cascade="all, delete-orphan", order_by="NumeroProtocolo.numero")


class NumeroProtocolo(Base):
    """Um número da sequência: livre, reservado, utilizado (com documento) ou anulado."""
    __tablename__ = "protocolo_numeros"
    __table_args__ = (
        UniqueConstraint("sequencia_id", "numero", name="uq_protocolo_numeros_sequencia_numero"),
        Index("ix_protocolo_numeros_reservado_por", "reservado_por_id", "reservado_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sequencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("protocolo_sequencias.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    finalidade: Mapped[str] = mapped_column(Text, default="")
    reservado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    reservado_por_nome: Mapped[str] = mapped_column(String(200), default="")
    reservado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contrato_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos.id", ondelete="SET NULL"), index=True)
    anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Documento sigiloso: só quem reservou e o SuperRoot veem o conteúdo do arquivo (os dados e a linha do tempo seguem visíveis)
    sigiloso: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    anulado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por_nome: Mapped[str | None] = mapped_column(String(200))
    motivo_anulacao: Mapped[str | None] = mapped_column(Text)
    origem_sgi_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    sequencia: Mapped[SequenciaProtocolo] = relationship(back_populates="numeros")
    anexo: Mapped[Anexo | None] = relationship(foreign_keys=[anexo_id])
    eventos: Mapped[list["EventoProtocolo"]] = relationship(back_populates="numero", cascade="all, delete-orphan", order_by="EventoProtocolo.ocorrido_em")

    @property
    def estado(self) -> str:
        """`anulado` prevalece; depois `utilizado` (tem documento), `reservado` e `livre`."""
        if self.anulado_em is not None:
            return "anulado"
        if self.anexo_id is not None:
            return "utilizado"
        return "reservado" if self.reservado_em is not None else "livre"


class EventoProtocolo(Base):
    """Linha do tempo de um número. Visível para quem tem acesso ao Protocolo, inclusive em documentos sigilosos."""
    __tablename__ = "protocolo_eventos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    numero_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("protocolo_numeros.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(12))
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(200), default="")
    texto: Mapped[str] = mapped_column(Text, default="")
    dados: Mapped[dict | None] = mapped_column(TipoJson)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    numero: Mapped[NumeroProtocolo] = relationship(back_populates="eventos")
