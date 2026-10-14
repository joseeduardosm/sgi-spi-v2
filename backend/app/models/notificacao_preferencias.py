# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas das preferências de notificação (canais por evento, configuração, navegadores, silenciados e obrigatórias).
"""Preferências das Notificações.

- `PreferenciaNotificacao`: um canal ligado para um evento. **Existir a linha = ligado**; sem linha = desligado, então todo usuário
  (inclusive os antigos) começa com tudo desmarcado.
- `ConfigNotificacaoUsuario`: frequência do e-mail (imediato, resumo diário ou semanal) e o "não perturbe".
- `InscricaoNavegador`: um navegador inscrito no Web Push (um usuário pode ter vários).
- `NotificacaoSilenciada`: contrato ou tarefa que a pessoa não quer mais receber pelos canais externos (a caixa continua recebendo).
- `NotificacaoObrigatoria`: evento + canal imposto pela administração a um setor ou usuário.
"""

import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc

CANAIS_BANCO = ("email", "navegador", "desktop")
FREQUENCIAS_EMAIL = ("imediato", "diario", "semanal")
TIPOS_SILENCIADO = ("contrato", "tarefa")


def _lista_sql(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class PreferenciaNotificacao(Base):
    """Canal ligado por um usuário para um evento."""
    __tablename__ = "notificacoes_preferencias"
    __table_args__ = (
        UniqueConstraint("usuario_id", "evento", "canal", name="uq_notificacoes_preferencias_usuario_evento_canal"),
        CheckConstraint(f"canal IN ({_lista_sql(CANAIS_BANCO)})", name="ck_notificacoes_preferencias_canal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    evento: Mapped[str] = mapped_column(String(60))
    canal: Mapped[str] = mapped_column(String(10))


class ConfigNotificacaoUsuario(Base):
    """Configuração de notificações de um usuário (uma linha por usuário, criada na primeira gravação)."""
    __tablename__ = "notificacoes_config_usuario"
    __table_args__ = (CheckConstraint(f"frequencia_email IN ({_lista_sql(FREQUENCIAS_EMAIL)})", name="ck_notificacoes_config_usuario_frequencia"),)

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    frequencia_email: Mapped[str] = mapped_column(String(10), default="imediato", server_default="imediato")
    # Não perturbe (horário de São Paulo): vale para navegador e desktop; o e-mail não é afetado. Sem início e fim = desligado
    silencio_inicio: Mapped[time | None] = mapped_column(Time)
    silencio_fim: Mapped[time | None] = mapped_column(Time)
    silencio_fins_de_semana: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class InscricaoNavegador(Base):
    """Navegador inscrito para receber notificações (Web Push)."""
    __tablename__ = "notificacoes_inscricoes_navegador"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))
    # Navegador e sistema (ex.: "Chrome no Windows"), para a pessoa reconhecer o aparelho
    rotulo: Mapped[str] = mapped_column(String(200), default="")
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    ultimo_envio_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    falhas_seguidas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class NotificacaoSilenciada(Base):
    """Contrato ou tarefa silenciado: sem e-mail, navegador nem desktop (a caixa continua recebendo)."""
    __tablename__ = "notificacoes_silenciados"
    __table_args__ = (
        UniqueConstraint("usuario_id", "tipo", "alvo_id", name="uq_notificacoes_silenciados_usuario_tipo_alvo"),
        CheckConstraint(f"tipo IN ({_lista_sql(TIPOS_SILENCIADO)})", name="ck_notificacoes_silenciados_tipo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(10))
    alvo_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    # Texto mostrado na lista de silenciados (ex.: "Contrato 012/2026"); o contrato ou a tarefa pode já não existir
    rotulo: Mapped[str] = mapped_column(String(300), default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class NotificacaoObrigatoria(Base):
    """Evento + canal imposto pela administração a um setor inteiro ou a um usuário (a pessoa não consegue desligar)."""
    __tablename__ = "notificacoes_obrigatorias"
    __table_args__ = (
        CheckConstraint(f"canal IN ({_lista_sql(CANAIS_BANCO)})", name="ck_notificacoes_obrigatorias_canal"),
        CheckConstraint("(setor_id IS NULL) <> (usuario_id IS NULL)", name="ck_notificacoes_obrigatorias_alvo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evento: Mapped[str] = mapped_column(String(60))
    canal: Mapped[str] = mapped_column(String(10))
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    criada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
