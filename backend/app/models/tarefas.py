# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do Módulo Tarefas (equipes, tarefas, participantes, linha do tempo, marcadores e checklist).
"""Módulo Tarefas.

- `EquipeTarefas`: equipe própria do módulo (independente dos setores), com dono, líderes, membros e equipe pai.
- `Tarefa`: a tarefa, com pipeline A fazer → Em andamento → Em validação → Concluída, prazo atual e **prazo original**,
  datas de cada etapa e `versao` (concorrência otimista).
- `ParticipanteTarefa`: todos os envolvidos (o responsável também é participante); a carga conta para cada um.
- `EventoTarefa`: linha do tempo append-only (criação, edição, status, prazo, transferência, comentário…). Guarda o
  nome do autor como retrato (o histórico continua legível se o usuário sair) e `dados` com de/para e justificativas.
- `MarcadorTarefa`: etiqueta por equipe (ou global, sem equipe); `ItemChecklistTarefa`: checklist da tarefa.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON, BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc

STATUS_TAREFA = ("a_fazer", "em_andamento", "em_validacao", "concluida")
PRIORIDADES_TAREFA = ("baixa", "normal", "alta", "critica")
TIPOS_EVENTO_TAREFA = (
    "criada", "editada", "status", "entregue", "validada", "devolvida", "reaberta", "prazo", "transferida",
    "comentario", "participantes", "marcadores", "checklist", "removido", "escalonada",
)


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class EquipeTarefas(Base):
    """Equipe do módulo: o dono governa a composição; os líderes validam, devolvem e reabrem tarefas da equipe."""
    __tablename__ = "tarefas_equipes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(150))
    dono_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    equipe_pai_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="SET NULL"))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    membros: Mapped[list["MembroEquipeTarefas"]] = relationship(back_populates="equipe", cascade="all, delete-orphan", lazy="selectin")
    lideres: Mapped[list["LiderEquipeTarefas"]] = relationship(back_populates="equipe", cascade="all, delete-orphan", lazy="selectin")


class MembroEquipeTarefas(Base):
    __tablename__ = "tarefas_equipes_membros"
    __table_args__ = (UniqueConstraint("equipe_id", "usuario_id", name="uq_tarefas_equipes_membros"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    equipe: Mapped[EquipeTarefas] = relationship(back_populates="membros")


class LiderEquipeTarefas(Base):
    __tablename__ = "tarefas_equipes_lideres"
    __table_args__ = (UniqueConstraint("equipe_id", "usuario_id", name="uq_tarefas_equipes_lideres"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    equipe: Mapped[EquipeTarefas] = relationship(back_populates="lideres")


class Tarefa(Base):
    __tablename__ = "tarefas"
    __table_args__ = (
        CheckConstraint(f"status IN ({_lista(STATUS_TAREFA)})", name="ck_tarefas_status"),
        CheckConstraint(f"prioridade IN ({_lista(PRIORIDADES_TAREFA)})", name="ck_tarefas_prioridade"),
        Index("ix_tarefas_responsavel_status", "responsavel_id", "status"),
        Index("ix_tarefas_equipe_status", "equipe_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Número público (#123), atribuído pelo serviço (maior + 1); os migrados mantêm o número do sistema anterior
    numero: Mapped[int] = mapped_column(Integer, unique=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str] = mapped_column(Text, default="")
    equipe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="SET NULL"), index=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    prazo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Prazo definido na criação: mostra quanto a tarefa foi prorrogada
    prazo_original: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prioridade: Mapped[str] = mapped_column(String(10), default="normal")
    status: Mapped[str] = mapped_column(String(15), default="a_fazer")
    # Ordem manual (arrastar na lista); menor aparece antes
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    # Datas de cada etapa do pipeline e tempo acumulado em andamento (segundos)
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    em_andamento_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    segundos_em_andamento: Mapped[int] = mapped_column(BigInteger, default=0)
    entregue_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    versao: Mapped[int] = mapped_column(Integer, default=1)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    equipe: Mapped[EquipeTarefas | None] = relationship(lazy="joined")
    participantes: Mapped[list["ParticipanteTarefa"]] = relationship(back_populates="tarefa", cascade="all, delete-orphan", lazy="selectin")
    marcadores: Mapped[list["MarcadorTarefa"]] = relationship(secondary="tarefas_marcadores_vinculos", lazy="selectin")
    checklist: Mapped[list["ItemChecklistTarefa"]] = relationship(
        back_populates="tarefa", cascade="all, delete-orphan", order_by="ItemChecklistTarefa.posicao", lazy="selectin"
    )


class ParticipanteTarefa(Base):
    __tablename__ = "tarefas_participantes"
    __table_args__ = (UniqueConstraint("tarefa_id", "usuario_id", name="uq_tarefas_participantes"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    tarefa: Mapped[Tarefa] = relationship(back_populates="participantes")


class EventoTarefa(Base):
    """Evento da linha do tempo (nunca é editado; remoção só lógica, pelo SuperRoot, com motivo)."""
    __tablename__ = "tarefas_eventos"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista(TIPOS_EVENTO_TAREFA)})", name="ck_tarefas_eventos_tipo"),
        Index("ix_tarefas_eventos_tarefa_em", "tarefa_id", "criado_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(15))
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(200))
    titulo: Mapped[str] = mapped_column(String(300), default="")
    texto: Mapped[str] = mapped_column(Text, default="")
    # De/para, prazos, justificativa, destinatário da transferência etc.
    dados: Mapped[dict] = mapped_column(JSON, default=dict)
    removido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removido_por_nome: Mapped[str | None] = mapped_column(String(200))
    motivo_remocao: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    anexos: Mapped[list["AnexoEventoTarefa"]] = relationship(back_populates="evento", cascade="all, delete-orphan", lazy="selectin")


class AnexoEventoTarefa(Base):
    __tablename__ = "tarefas_eventos_anexos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_eventos.id", ondelete="CASCADE"), index=True)
    anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="CASCADE"))
    evento: Mapped[EventoTarefa] = relationship(back_populates="anexos")
    anexo: Mapped["Anexo"] = relationship(lazy="joined")  # noqa: F821


class MarcadorTarefa(Base):
    """Etiqueta por equipe (criada pela liderança) ou global (sem equipe)."""
    __tablename__ = "tarefas_marcadores"
    __table_args__ = (UniqueConstraint("equipe_id", "nome", name="uq_tarefas_marcadores_equipe_nome"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    equipe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    cor: Mapped[str] = mapped_column(String(7), default="#5364ce")


class VinculoMarcadorTarefa(Base):
    __tablename__ = "tarefas_marcadores_vinculos"

    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), primary_key=True)
    marcador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_marcadores.id", ondelete="CASCADE"), primary_key=True)


class ItemChecklistTarefa(Base):
    __tablename__ = "tarefas_checklist"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), index=True)
    texto: Mapped[str] = mapped_column(String(300))
    posicao: Mapped[int] = mapped_column(Integer, default=0)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    tarefa: Mapped[Tarefa] = relationship(back_populates="checklist")
