# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela das colunas que cada usuário escolheu mostrar nas listagens (como as preferências de exibição do GLPI).
"""Preferência de colunas: por usuário e por tela, a lista ordenada das colunas que a pessoa quer ver na listagem.

`usuario_id` nulo = **visão global** da tela (definida pelo administrador): vale para quem não tem visão pessoal.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson


class PreferenciaColunas(Base):
    """Colunas escolhidas por um usuário para uma tela (ex.: `patrimonio.bens`), na ordem de exibição."""

    __tablename__ = "usuarios_preferencias_colunas"
    __table_args__ = (
        UniqueConstraint("usuario_id", "tela", name="uq_usuarios_preferencias_colunas_tela"),
        # Só uma visão global por tela (o UNIQUE acima não impede repetir quando o usuário é nulo)
        Index("uq_usuarios_preferencias_colunas_global", "tela", unique=True, postgresql_where=text("usuario_id IS NULL"), sqlite_where=text("usuario_id IS NULL")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    # Identificador da tela, escolhido pelo módulo (ex.: `patrimonio.bens`)
    tela: Mapped[str] = mapped_column(String(60))
    # Lista de ids de coluna, na ordem; o frontend ignora ids que a tela não conhece mais
    colunas: Mapped[list] = mapped_column(TipoJson)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
