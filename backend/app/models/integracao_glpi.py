# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas da integração com o GLPI (configuração e chamados abertos pelo SGI).
"""Integração com o GLPI (helpdesk): configuração única e registro dos chamados abertos pelo SGI."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class IntegracaoGlpi(Base):
    """Configuração da integração (uma única linha). Os tokens ficam cifrados e nunca voltam pela API."""

    __tablename__ = "integracao_glpi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    # Endereço do GLPI, sem o /apirest.php (ex.: https://chamados.spi.sp.gov.br)
    url_base: Mapped[str] = mapped_column(String(300), default="")
    # App-Token do cliente de API (opcional: o GLPI também restringe por IP) e user_token da conta de serviço
    app_token_cifrado: Mapped[str] = mapped_column(String(600), default="")
    user_token_cifrado: Mapped[str] = mapped_column(String(600), default="")
    # Valores do chamado: tipo 1 = incidente; urgência 3 = média; origem 1 = "Helpdesk"
    tipo_padrao: Mapped[int] = mapped_column(Integer, default=1)
    urgencia_padrao: Mapped[int] = mapped_column(Integer, default=3)
    origem_id: Mapped[int] = mapped_column(Integer, default=1)
    # Como o formulário "Informática" (id 3) do GLPI monta o chamado: título "<prefixo> | <assunto>", grupo atribuído (SUPORTE = 4),
    # SLA de atendimento (2) e de solução (1) e modelo de chamado (1). Os ids vêm do próprio GLPI.
    prefixo_titulo: Mapped[str] = mapped_column(String(80), default="Informática")
    grupo_atribuido_id: Mapped[int | None] = mapped_column(Integer, default=4)
    sla_atendimento_id: Mapped[int | None] = mapped_column(Integer, default=2)
    sla_solucao_id: Mapped[int | None] = mapped_column(Integer, default=1)
    template_id: Mapped[int | None] = mapped_column(Integer, default=1)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
    atualizado_por: Mapped[str] = mapped_column(String(150), default="")


class ChamadoGlpi(Base):
    """Um chamado aberto pelo SGI no GLPI (para o limite por hora e a lista "meus chamados")."""

    __tablename__ = "chamados_glpi"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    glpi_id: Mapped[int] = mapped_column(Integer)
    assunto: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(400))
    aberto_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, index=True)
