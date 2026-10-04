# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do Diretório (favoritos de ramais e mural de parabéns).
"""Diretório de ramais e aniversariantes.

- `FavoritoDiretorio`: contatos que cada usuário fixou no topo da própria lista de ramais.
- `ParabensAniversario`: recado deixado por um colega no mural de parabéns de um aniversariante (um por autor e por ano).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class FavoritoDiretorio(Base):
    """Par (usuário, contato favorito)."""
    __tablename__ = "diretorio_favoritos"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    favorito_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class ParabensAniversario(Base):
    """Recado no mural de parabéns de um aniversariante."""
    __tablename__ = "diretorio_parabens"
    __table_args__ = (UniqueConstraint("aniversariante_id", "autor_id", "ano", name="uq_diretorio_parabens_autor_ano"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    aniversariante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    # Retrato do nome no momento do recado (o mural continua legível se o cadastro mudar)
    autor_nome: Mapped[str] = mapped_column(String(200))
    # Ano do aniversário homenageado: cada ano tem um mural novo
    ano: Mapped[int] = mapped_column(Integer)
    texto: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
