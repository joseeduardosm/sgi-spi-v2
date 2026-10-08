# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela da configuração da integração com o BookStack (manuais dentro do portal).
"""Integração com o BookStack: configuração única (endereço e token de API da conta de serviço, cifrados)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class IntegracaoBookstack(Base):
    """Configuração da integração (uma única linha). O token fica cifrado e nunca volta pela API."""

    __tablename__ = "integracao_bookstack"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    # Endereço do BookStack, sem barra final (ex.: https://instrucoes.spi.sp.gov.br)
    url_base: Mapped[str] = mapped_column(String(300), default="")
    # Token de API da conta de serviço (somente leitura): ID e segredo, cifrados
    token_id_cifrado: Mapped[str] = mapped_column(String(600), default="")
    token_segredo_cifrado: Mapped[str] = mapped_column(String(600), default="")
    # Ids dos livros que o portal mostra, separados por vírgula (ex.: "147"); vazio = todos os que a conta de serviço enxerga
    livros_permitidos: Mapped[str] = mapped_column(String(200), default="")
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
    atualizado_por: Mapped[str] = mapped_column(String(150), default="")
