# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela com a configuração do menu da barra lateral (ordem, grupos, nomes e itens ocultos).
"""Configuração do menu lateral escolhida pelo administrador (linha única)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class MenuConfiguracao(Base):
    """Linha única (`id = 1`): lista ordenada de nós do menu. Sem a linha, vale o menu padrão do código."""

    __tablename__ = "menu_configuracao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Lista de nós `{id, tipo, rotulo, pai_id, oculto, url, nova_aba}` (ver `schemas/menu.py`)
    itens: Mapped[list] = mapped_column(JSON, default=list)
    atualizado_por_nome: Mapped[str] = mapped_column(String(160), default="")
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
