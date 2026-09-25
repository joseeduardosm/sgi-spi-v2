# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela de configuração dos diretórios LDAP.
"""Configuração de um diretório LDAP/Active Directory.

Guarda como o portal se conecta ao AD para conferir as senhas corporativas e importar os
usuários, além do resultado do último teste de conexão e da última sincronização.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class DiretorioLdap(Base):
    """Um servidor LDAP/AD cadastrado pelo SuperRoot."""
    __tablename__ = "diretorios_ldap"
    # No máximo um diretório ativo (índice único parcial)
    __table_args__ = (
        Index(
            "ux_diretorios_ldap_unico_ativo",
            "ativo",
            unique=True,
            postgresql_where=text("ativo"),
            sqlite_where=text("ativo"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Endereço do servidor; porta 389 (LDAP) ou 636 (LDAPS, quando `usar_ssl`)
    nome: Mapped[str] = mapped_column(String(100))
    servidor: Mapped[str] = mapped_column(String(255))
    porta: Mapped[int] = mapped_column(Integer, default=389)
    usar_ssl: Mapped[bool] = mapped_column(Boolean, default=False)
    # Onde procurar os usuários (Base DN) e a conta técnica usada para consultar o diretório
    base_dn: Mapped[str] = mapped_column(String(500))
    bind_dn: Mapped[str] = mapped_column(String(500))
    # Senha da conta técnica cifrada com Fernet (app.core.criptografia). Nunca devolvida pela API.
    senha_bind_cifrada: Mapped[str] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)

    # Resultado do último teste de conexão (exibido na tela de administração)
    ultimo_teste_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_teste_ok: Mapped[bool | None] = mapped_column(Boolean)
    ultima_latencia_ms: Mapped[int | None] = mapped_column(Integer)
    ultimo_erro: Mapped[str | None] = mapped_column(Text)

    # Resultado da última sincronização de usuários
    ultima_sincronizacao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultima_sincronizacao_ok: Mapped[bool | None] = mapped_column(Boolean)
    ultima_sincronizacao_mensagem: Mapped[str | None] = mapped_column(Text)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
