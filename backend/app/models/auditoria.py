# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela de auditoria das operações e do histórico por campo.
"""Registro de auditoria das operações administrativas e do histórico por campo.

Toda operação relevante (criar, alterar, excluir, concluir etapa...) grava uma linha aqui:
quem fez, quando, o quê e sobre qual registro. É com base nela que a tela mostra o histórico
"de → para" de cada campo do contrato.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc

# JSONB no PostgreSQL; JSON genérico no SQLite dos testes
TipoJson = JSON().with_variant(JSONB(), "postgresql")


class RegistroAuditoria(Base):
    """Uma operação registrada na auditoria."""
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, index=True)
    # Login do autor, gravado como texto para continuar legível mesmo se o usuário for excluído
    autor: Mapped[str] = mapped_column(String(150))
    # Id do usuário autor, quando a operação vem de um usuário autenticado
    autor_id: Mapped[int | None] = mapped_column(Integer)
    # Código da ação (ex.: `contrato.alterar`) e descrição legível do registro afetado
    acao: Mapped[str] = mapped_column(String(80), index=True)
    alvo: Mapped[str] = mapped_column(String(255))
    # Texto livre com detalhes adicionais (formato antigo, anterior ao campo estruturado `dados`)
    detalhes: Mapped[str | None] = mapped_column(Text)
    # Identificação estruturada do alvo (ex.: alvo_tipo="contrato", alvo_id=<uuid>), usada no
    # histórico por campo. `dados` guarda o conteúdo do ato; nas alterações, o formato é
    # {"campos": {"nome_do_campo": {"de": ..., "para": ...}}}.
    alvo_tipo: Mapped[str | None] = mapped_column(String(60))
    alvo_id: Mapped[str | None] = mapped_column(String(64))
    dados: Mapped[dict[str, Any] | None] = mapped_column(TipoJson)


# Acelera a consulta do histórico de um registro, em ordem cronológica
Index("ix_auditoria_alvo", RegistroAuditoria.alvo_tipo, RegistroAuditoria.alvo_id, RegistroAuditoria.ocorrido_em)
