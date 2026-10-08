# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas dos atalhos fixos da barra lateral (categorias e atalhos, internos e externos).
"""Atalhos fixos para todos os usuários: categorias dobráveis com links para telas do SGI ou endereços externos."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc


class CategoriaAtalho(Base):
    """Categoria de atalhos (aparece como uma seção dobrável dentro de "Atalhos" na barra lateral)."""

    __tablename__ = "atalhos_categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    atalhos: Mapped[list["AtalhoFixo"]] = relationship(back_populates="categoria", cascade="all, delete-orphan", order_by="AtalhoFixo.ordem, AtalhoFixo.id")


class AtalhoFixo(Base):
    """Um atalho: título e destino (rota interna começando por `/` ou endereço `http(s)://`)."""

    __tablename__ = "atalhos_fixos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("atalhos_categorias.id", ondelete="CASCADE"), index=True)
    titulo: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(500))
    # Externos abrem em nova aba por padrão; internos, na mesma
    nova_aba: Mapped[bool] = mapped_column(Boolean, default=False)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    categoria: Mapped[CategoriaAtalho] = relationship(back_populates="atalhos")


# Nome da categoria único sem diferenciar maiúsculas (evita "TI" e "ti" lado a lado)
from sqlalchemy import Index  # noqa: E402

Index("ux_atalhos_categorias_nome", func.lower(CategoriaAtalho.nome), unique=True)
