# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas de empresas contratadas e prepostos.
"""Empresas contratadas e seus prepostos (contatos da empresa, não usuários do portal).

CNPJ e CPF são gravados só com dígitos; a formatação (pontos, barra e traço) é feita na tela.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc


class EmpresaContratada(Base):
    """Empresa contratada (pessoa jurídica), identificada pelo CNPJ único."""
    __tablename__ = "contratos_empresas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Somente dígitos (14)
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    razao_social: Mapped[str] = mapped_column(String(250))
    nome_fantasia: Mapped[str] = mapped_column(String(250), default="")
    endereco: Mapped[str] = mapped_column(String(500), default="")
    # Empresa inativa não aparece nas opções do cadastro de contrato, mas continua nos contratos antigos
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    # Prepostos da empresa: `delete-orphan` apaga o preposto que for removido da lista
    prepostos: Mapped[list["PrepostoEmpresa"]] = relationship(
        back_populates="empresa", cascade="all, delete-orphan", order_by="PrepostoEmpresa.nome"
    )


class PrepostoEmpresa(Base):
    """Preposto: representante da empresa junto à Administração."""
    __tablename__ = "contratos_empresas_prepostos"
    # O mesmo CPF não pode aparecer duas vezes na mesma empresa (mas pode em empresas diferentes)
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
