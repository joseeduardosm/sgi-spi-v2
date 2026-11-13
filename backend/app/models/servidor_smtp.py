"""
===============================================================================
ARQUIVO: servidor_smtp.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Definir a tabela de configuração dos servidores SMTP, usados pelo portal
para enviar e-mails.

RESUMO TÉCNICO:
Modelo ServidorSmtp (tabela servidores_smtp): endereço, porta, segurança
(nenhuma, STARTTLS ou SSL), conta de autenticação com senha cifrada (Fernet),
remetente, tempo limite e o resultado do último teste de conexão e do último
e-mail de teste. Um índice único parcial garante no máximo um servidor
ativo. A propriedade possui_senha expõe só se há senha, nunca o valor.

FINALIDADE DE NEGÓCIO:
Permitir que o SuperRoot (administrador) troque o servidor de e-mail pela
tela, sem mexer em código, e comprove que o envio funciona antes de usar.
Notificações, avisos e e-mails dos módulos dependem desta configuração.

CONTEXTO NO SISTEMA:
Usado pelo serviço de e-mail e pelas rotas de servidores SMTP; o formato da
API está em schemas/smtp.py. A cifra da senha usa app.core.criptografia.

===============================================================================
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc

# Segurança da conexão: sem cifra, STARTTLS (sobe para TLS na porta 587/25) ou SSL direto (porta 465)
SEGURANCAS_SMTP = ("nenhuma", "starttls", "ssl")


class ServidorSmtp(Base):
    """Um servidor SMTP cadastrado pelo SuperRoot. O ativo é o usado pelo sistema para enviar e-mails.

    SMTP é o protocolo de envio de e-mail. SuperRoot é o papel de administrador do portal.
    Podem existir vários cadastrados (ex.: um de reserva), mas só um fica ativo por vez.
    """
    __tablename__ = "servidores_smtp"
    __table_args__ = (
        CheckConstraint("seguranca IN ('nenhuma', 'starttls', 'ssl')", name="ck_servidores_smtp_seguranca"),
        # No máximo um servidor ativo (índice único parcial: a unicidade só vale nas linhas em que
        # ativo é verdadeiro, então os inativos podem se repetir à vontade)
        Index("ux_servidores_smtp_unico_ativo", "ativo", unique=True, postgresql_where=text("ativo"), sqlite_where=text("ativo")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(100))
    # Endereço e porta do servidor (ex.: smtp.office365.com:587 com STARTTLS)
    servidor: Mapped[str] = mapped_column(String(255))
    porta: Mapped[int] = mapped_column(Integer, default=587)
    seguranca: Mapped[str] = mapped_column(String(10), default="starttls")
    # Conta de autenticação; vazia = servidor sem autenticação (relay interno)
    usuario: Mapped[str] = mapped_column(String(254), default="")
    # Senha cifrada com Fernet (app.core.criptografia). Nunca devolvida pela API.
    senha_cifrada: Mapped[str | None] = mapped_column(Text)
    # Remetente das mensagens (campo "De") e, opcionalmente, para onde vão as respostas
    remetente_email: Mapped[str] = mapped_column(String(254))
    remetente_nome: Mapped[str] = mapped_column(String(150), default="")
    responder_para: Mapped[str] = mapped_column(String(254), default="")
    tempo_limite_segundos: Mapped[int] = mapped_column(Integer, default=20)
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)

    # Resultado do último teste de conexão (conexão + segurança + autenticação)
    ultimo_teste_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_teste_ok: Mapped[bool | None] = mapped_column(Boolean)
    ultima_latencia_ms: Mapped[int | None] = mapped_column(Integer)
    ultimo_erro: Mapped[str | None] = mapped_column(Text)

    # Último e-mail de teste enviado (prova de ponta a ponta)
    ultimo_envio_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_envio_ok: Mapped[bool | None] = mapped_column(Boolean)
    ultimo_envio_para: Mapped[str | None] = mapped_column(String(254))
    ultimo_envio_mensagem: Mapped[str | None] = mapped_column(Text)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    # `@property` cria um atributo calculado (lido como servidor.possui_senha, sem parênteses),
    # que o schema de leitura da API usa no lugar da senha
    @property
    def possui_senha(self) -> bool:
        """Há senha gravada (a API mostra só isso, nunca o valor)."""
        return bool(self.senha_cifrada)
