# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do módulo Reserva de Espaços (salas, anfiteatro, reservas, fiscais e linha do tempo).
"""Módulo Reserva de Espaços (migrado do 10.23.1.243).

- `EspacoReservavel`: sala/anfiteatro que pode ser reservado (cor na agenda, capacidade, equipamentos).
- `ReservaEspaco`: pedido de uso de um espaço em uma data/horário; várias ocorrências de uma recorrência compartilham o `serie_id`.
- `EventoReservaEspaco`: linha do tempo da reserva (criação, edição, deferimento, indeferimento, cancelamento, lembrete).
- `FiscalReservaEspacos`: quem analisa a fila (substitui o grupo "Fiscais Salas" do sistema antigo).
- `ConfiguracaoReservaEspacos`: linha única com horário de funcionamento, antecedência mínima e duração máxima.
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson

STATUS_AGUARDANDO = "AGUARDANDO_APROVACAO"
STATUS_DEFERIDA = "DEFERIDA"
STATUS_INDEFERIDA = "INDEFERIDA"
STATUS_CANCELADA = "CANCELADA"
STATUS = (STATUS_AGUARDANDO, STATUS_DEFERIDA, STATUS_INDEFERIDA, STATUS_CANCELADA)
TIPOS_EVENTO = ("CRIACAO", "EDICAO", "CANCELAMENTO", "DEFERIMENTO", "INDEFERIMENTO", "LEMBRETE")


class EspacoReservavel(Base):
    """Sala, anfiteatro ou outro espaço reservável."""
    __tablename__ = "reserva_espacos_espacos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    localizacao: Mapped[str] = mapped_column(String(200), default="")
    cor: Mapped[str] = mapped_column(String(7), default="#0b5cad")
    capacidade: Mapped[int | None] = mapped_column(Integer)
    equipamentos: Mapped[str] = mapped_column(Text, default="")
    descricao: Mapped[str] = mapped_column(Text, default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Id do objeto no sistema antigo (recarga idempotente da migração)
    origem_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)


class ReservaEspaco(Base):
    """Pedido de reserva de um espaço em uma data e horário."""
    __tablename__ = "reserva_espacos_reservas"
    __table_args__ = (
        CheckConstraint("hora_fim > hora_inicio", name="ck_reserva_espacos_horario"),
        Index("ix_reserva_espacos_espaco_data", "espaco_id", "data", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    espaco_id: Mapped[int] = mapped_column(ForeignKey("reserva_espacos_espacos.id", ondelete="RESTRICT"))
    data: Mapped[date] = mapped_column(Date, index=True)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fim: Mapped[time] = mapped_column(Time)
    titulo: Mapped[str] = mapped_column(String(200))
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    responsavel_nome: Mapped[str] = mapped_column(String(200), default="")
    observacoes: Mapped[str] = mapped_column(Text, default="")
    participantes: Mapped[int | None] = mapped_column(Integer)
    solicitante_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    solicitante_nome: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(30), default=STATUS_AGUARDANDO, index=True)
    fiscal_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    fiscal_nome: Mapped[str] = mapped_column(String(200), default="")
    justificativa: Mapped[str] = mapped_column(Text, default="")
    serie_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    lembrete_enviado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    origem_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    espaco: Mapped[EspacoReservavel] = relationship()
    eventos: Mapped[list["EventoReservaEspaco"]] = relationship(
        back_populates="reserva", cascade="all, delete-orphan", order_by="EventoReservaEspaco.criado_em, EventoReservaEspaco.id"
    )


class EventoReservaEspaco(Base):
    """Linha do tempo de uma reserva."""
    __tablename__ = "reserva_espacos_eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reserva_id: Mapped[int] = mapped_column(ForeignKey("reserva_espacos_reservas.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    usuario_nome: Mapped[str] = mapped_column(String(200), default="")
    detalhes: Mapped[dict | None] = mapped_column(TipoJson)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    reserva: Mapped[ReservaEspaco] = relationship(back_populates="eventos")


class FiscalReservaEspacos(Base):
    """Usuário que analisa as solicitações, cadastra espaços e vê o painel."""
    __tablename__ = "reserva_espacos_fiscais"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class ConfiguracaoReservaEspacos(Base):
    """Regras gerais (linha única, id = 1)."""
    __tablename__ = "reserva_espacos_configuracao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    hora_abertura: Mapped[time] = mapped_column(Time, default=time(7, 0))
    hora_fechamento: Mapped[time] = mapped_column(Time, default=time(19, 0))
    # Antecedência mínima, em horas, para o solicitante pedir (fiscal não tem a restrição); 0 = sem limite
    antecedencia_minima_horas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Duração máxima de cada reserva, em horas; 0 = sem limite
    duracao_maxima_horas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
