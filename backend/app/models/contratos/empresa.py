"""Empresas contratadas e seus prepostos (contatos da empresa, não usuários do portal)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc


class EmpresaContratada(Base):
    __tablename__ = "contratos_empresas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Somente dígitos (14)
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    razao_social: Mapped[str] = mapped_column(String(250))
    nome_fantasia: Mapped[str] = mapped_column(String(250), default="")
    endereco: Mapped[str] = mapped_column(String(500), default="")
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    prepostos: Mapped[list["PrepostoEmpresa"]] = relationship(
        back_populates="empresa", cascade="all, delete-orphan", order_by="PrepostoEmpresa.nome"
    )


class PrepostoEmpresa(Base):
    __tablename__ = "contratos_empresas_prepostos"
    __table_args__ = (UniqueConstraint("empresa_id", "cpf"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_empresas.id", ondelete="CASCADE"), index=True)
    # Somente dígitos (11)
    cpf: Mapped[str] = mapped_column(String(11))
    nome: Mapped[str] = mapped_column(String(200))
    telefone: Mapped[str] = mapped_column(String(30), default="")
    email: Mapped[str] = mapped_column(String(250), default="")
    cargo: Mapped[str] = mapped_column(String(150), default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    empresa: Mapped[EmpresaContratada] = relationship(back_populates="prepostos")
