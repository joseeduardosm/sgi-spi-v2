"""
===============================================================================
ARQUIVO: reserva_espacos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Definir as tabelas do módulo Reserva de Espaços (migrado do sistema antigo
10.23.1.243): salas e anfiteatro, reservas, linha do tempo, fiscais e a
configuração geral de funcionamento.

RESUMO TÉCNICO:
Modelos SQLAlchemy 2 (Mapped/mapped_column):
- EspacoReservavel: sala/anfiteatro reservável (cor na agenda, capacidade,
  equipamentos, ativo).
- ReservaEspaco: pedido de uso em uma data/horário; as ocorrências de uma
  recorrência compartilham o serie_id. CheckConstraint garante fim > início.
- EventoReservaEspaco: linha do tempo (criação, edição, deferimento,
  indeferimento, cancelamento, lembrete).
- FiscalReservaEspacos: quem analisa a fila (substitui o grupo "Fiscais
  Salas" do sistema antigo).
- ConfiguracaoReservaEspacos: linha única com horário de funcionamento,
  antecedência mínima e duração máxima.

FINALIDADE DE NEGÓCIO:
Organizar o uso das salas de reunião e do anfiteatro da SPI: quem pede,
quem aprova (deferimento pelo fiscal), quando e com que histórico, evitando
choque de horário e mantendo o registro de cada decisão.

CONTEXTO NO SISTEMA:
Usado por app/services/reserva_espacos e pelas rotas do módulo Reserva de
Espaços; ligado a usuarios (solicitante, responsável, fiscal). O campo
origem_id permite recarregar a migração do sistema antigo sem duplicar.
Tabelas criadas pelas migrações em backend/alembic/versions/.

===============================================================================
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson

# Situações de uma reserva. Toda reserva nasce aguardando a análise do fiscal, que defere (aprova)
# ou indefere (recusa); o solicitante ou o fiscal podem cancelar. Os valores ficam gravados no banco.
STATUS_AGUARDANDO = "AGUARDANDO_APROVACAO"
STATUS_DEFERIDA = "DEFERIDA"
STATUS_INDEFERIDA = "INDEFERIDA"
STATUS_CANCELADA = "CANCELADA"
STATUS = (STATUS_AGUARDANDO, STATUS_DEFERIDA, STATUS_INDEFERIDA, STATUS_CANCELADA)
# Tipos de evento da linha do tempo (EventoReservaEspaco.tipo)
TIPOS_EVENTO = ("CRIACAO", "EDICAO", "CANCELAMENTO", "DEFERIMENTO", "INDEFERIMENTO", "LEMBRETE")


class EspacoReservavel(Base):
    """Sala, anfiteatro ou outro espaço reservável.

    Cada classe que herda de `Base` vira uma tabela (nome em `__tablename__`). Os atributos
    `Mapped[tipo] = mapped_column(...)` são as colunas: `Mapped` diz o tipo em Python (e se aceita
    nulo, com `| None`) e `mapped_column` configura a coluna no banco (tipo SQL, padrão, índice).
    `ativo = False` tira o espaço da agenda sem apagar as reservas antigas.
    """
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
    """Pedido de reserva de um espaço em uma data e horário.

    Guarda o nome do solicitante, do responsável e do fiscal além do id: se a conta for excluída
    (`ondelete="SET NULL"` zera o id), o nome continua aparecendo no histórico.
    """
    __tablename__ = "reserva_espacos_reservas"
    # Restrições no próprio banco: o horário final precisa ser depois do inicial, e o índice
    # acelera a busca de conflitos (mesmo espaço, mesma data, por status)
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
    # Reservas recorrentes: todas as ocorrências da mesma série têm o mesmo serie_id (vazio = avulsa)
    serie_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    # Marca que o lembrete da véspera (aviso no sistema e por e-mail) já saiu, para não repetir
    lembrete_enviado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    origem_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    # `relationship` não cria coluna: dá acesso ao objeto ligado pela chave estrangeira
    # (reserva.espaco) ou à lista de filhos (reserva.eventos). `cascade="all, delete-orphan"`
    # apaga os eventos junto com a reserva; `back_populates` mantém os dois lados sincronizados.
    espaco: Mapped[EspacoReservavel] = relationship()
    eventos: Mapped[list["EventoReservaEspaco"]] = relationship(
        back_populates="reserva", cascade="all, delete-orphan", order_by="EventoReservaEspaco.criado_em, EventoReservaEspaco.id"
    )


class EventoReservaEspaco(Base):
    """Linha do tempo de uma reserva: um registro por ação (tipo em `TIPOS_EVENTO`).

    `detalhes` é JSON livre (ex.: o que mudou numa edição ou a justificativa do indeferimento).
    """
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
    """Usuário que analisa as solicitações, cadastra espaços e vê o painel.

    A própria chave primária é o id do usuário: cada pessoa aparece no máximo uma vez.
    """
    __tablename__ = "reserva_espacos_fiscais"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class ConfiguracaoReservaEspacos(Base):
    """Regras gerais (linha única, id = 1)."""
    __tablename__ = "reserva_espacos_configuracao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Janela do dia em que as reservas podem acontecer (o serviço recusa horários fora dela)
    hora_abertura: Mapped[time] = mapped_column(Time, default=time(7, 0))
    hora_fechamento: Mapped[time] = mapped_column(Time, default=time(19, 0))
    # Antecedência mínima, em horas, para o solicitante pedir (fiscal não tem a restrição); 0 = sem limite
    antecedencia_minima_horas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Duração máxima de cada reserva, em horas; 0 = sem limite
    duracao_maxima_horas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
