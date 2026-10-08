# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a política de SLA (prazos de resposta e de resolução em dias úteis por módulo e prioridade).
"""Política de SLA: por módulo (`tarefas` ou `melhorias`) e, nas tarefas, por prioridade, quantos dias úteis valem para responder e para resolver."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc

MODULOS_SLA = ("tarefas", "melhorias")


class SlaPolitica(Base):
    """Uma linha da política: `modulo` + `prioridade` (vazia em Melhorias, que tem uma regra só)."""

    __tablename__ = "sla_politicas"
    __table_args__ = (
        UniqueConstraint("modulo", "prioridade", name="uq_sla_politicas_modulo_prioridade"),
        CheckConstraint("modulo IN ('tarefas', 'melhorias')", name="ck_sla_politicas_modulo"),
        CheckConstraint("dias_uteis_resposta >= 0 AND dias_uteis_resolucao >= dias_uteis_resposta", name="ck_sla_politicas_dias"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    modulo: Mapped[str] = mapped_column(String(20))
    # `baixa`, `normal`, `alta` ou `critica` nas tarefas; texto vazio em Melhorias (a unicidade vale para o par)
    prioridade: Mapped[str] = mapped_column(String(10), default="", server_default="")
    dias_uteis_resposta: Mapped[int] = mapped_column(Integer)
    dias_uteis_resolucao: Mapped[int] = mapped_column(Integer)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
