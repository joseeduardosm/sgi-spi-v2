# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas de setores e de seus membros.
"""Setores: unidades institucionais e grupos sistêmicos. Funcionam como grupos de acesso na ACL."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class Setor(Base):
    __tablename__ = "setores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    setor_pai_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="RESTRICT"), index=True)
    lider_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Sistêmico: grupo de acesso sem correspondência na estrutura institucional (ex.: "Auditores")
    sistemico: Mapped[bool] = mapped_column(Boolean, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)


Index("ux_setores_nome_minusculo", func.lower(Setor.nome), unique=True)


class MembroSetor(Base):
    __tablename__ = "membros_setor"

    setor_id: Mapped[int] = mapped_column(ForeignKey("setores.id", ondelete="CASCADE"), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
