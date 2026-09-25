"""Previsão orçamentária por vigência e Notas de Empenho (NE) com extrato.

Saldos não são gravados: saldo da NE = valor original − débitos do extrato.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.contratos.contrato import Contrato


class PrevisaoVigencia(Base):
    """Previsão de uma vigência. Depois de salva fica selada: só o SuperRoot altera."""

    __tablename__ = "contratos_previsoes"
    __table_args__ = (UniqueConstraint("contrato_id", "sequencia_vigencia"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    sequencia_vigencia: Mapped[int] = mapped_column(Integer)
    salva: Mapped[bool] = mapped_column(Boolean, default=False)
    salva_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    salva_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="previsoes")
    limites: Mapped[list["LimitePrevisao"]] = relationship(back_populates="previsao", cascade="all, delete-orphan")
    apontamentos: Mapped[list["ApontamentoPrevisao"]] = relationship(back_populates="previsao", cascade="all, delete-orphan")


class LimitePrevisao(Base):
    """Teto do item sob demanda na vigência (definido na prorrogação). Sem linha = quantidade original."""

    __tablename__ = "contratos_previsoes_limites"
    __table_args__ = (UniqueConstraint("previsao_id", "item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    previsao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_previsoes.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_itens.id", ondelete="CASCADE"), index=True)
    quantidade_total: Mapped[Decimal] = mapped_column(Numeric(18, 4))

    previsao: Mapped[PrevisaoVigencia] = relationship(back_populates="limites")


class ApontamentoPrevisao(Base):
    """Quantidade de um item sob demanda prevista para um mês (competência = dia 1)."""

    __tablename__ = "contratos_previsoes_apontamentos"
    __table_args__ = (UniqueConstraint("previsao_id", "item_id", "competencia"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    previsao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_previsoes.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_itens.id", ondelete="CASCADE"), index=True)
    competencia: Mapped[date] = mapped_column(Date)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(18, 4))

    previsao: Mapped[PrevisaoVigencia] = relationship(back_populates="apontamentos")


class NotaEmpenho(Base):
    __tablename__ = "contratos_notas_empenho"
    __table_args__ = (UniqueConstraint("contrato_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    numero: Mapped[str] = mapped_column(String(30))
    valor_original: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="notas_empenho")
    movimentos: Mapped[list["MovimentoNotaEmpenho"]] = relationship(
        back_populates="nota", cascade="all, delete-orphan", order_by="MovimentoNotaEmpenho.criado_em"
    )

    @property
    def consumido(self) -> Decimal:
        return sum((m.debito for m in self.movimentos), Decimal(0))

    @property
    def saldo(self) -> Decimal:
        return self.valor_original - self.consumido


class MovimentoNotaEmpenho(Base):
    """Lançamento imutável no extrato da NE.

    `pagamento`: débito positivo, lançado quando a Ordem Bancária da competência é anexada.
    `estorno`: débito negativo, lançado quando uma competência paga é reaberta (o pagamento
    original permanece no extrato, para manter o histórico).
    """

    __tablename__ = "contratos_notas_empenho_movimentos"
    __table_args__ = (CheckConstraint("tipo IN ('pagamento', 'estorno')", name="ck_contratos_ne_movimentos_tipo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nota_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_notas_empenho.id", ondelete="CASCADE"), index=True)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(40), default="pagamento")
    debito: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    justificativa: Mapped[str] = mapped_column(String(2000), default="", server_default="")
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    nota: Mapped[NotaEmpenho] = relationship(back_populates="movimentos")
