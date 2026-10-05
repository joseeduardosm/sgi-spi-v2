# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela das telas favoritas de cada usuário (atalhos no menu lateral).
"""Favoritos do menu: telas que o usuário fixou para abrir com um clique, em qualquer navegador ou aparelho."""

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base


class FavoritoMenu(Base):
    """Uma tela favorita do usuário (rota do Angular, com o rótulo mostrado no menu)."""

    __tablename__ = "usuarios_favoritos"
    __table_args__ = (UniqueConstraint("usuario_id", "rota", name="uq_usuarios_favoritos_rota"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    # Rota do Angular, com ou sem query string (ex.: `/contratos/ab12…`, `/ramais?q=Maria`)
    rota: Mapped[str] = mapped_column(String(300))
    rotulo: Mapped[str] = mapped_column(String(120))
    ordem: Mapped[int] = mapped_column(Integer, default=0)
