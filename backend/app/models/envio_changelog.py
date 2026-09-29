# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela dos e-mails de changelog (novidades do sistema) enviados pela mensageria.
"""E-mail de changelog: o registro de cada envio feito pela conta root na tela Mensageria.

O rascunho do próximo e-mail parte das entradas do `CHANGELOG.md` posteriores à última data já enviada a todos
(`ate_data`); envios de teste ficam registrados, mas não contam para essa data.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class EnvioChangelog(Base):
    """Um e-mail de changelog enviado: a todos os ativos, a usuários e setores escolhidos, ou só a um endereço de teste."""
    __tablename__ = "mensageria_envios_changelog"
    __table_args__ = (
        CheckConstraint("destino IN ('todos', 'teste', 'selecionados')", name="ck_mensageria_envios_changelog_destino"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assunto: Mapped[str] = mapped_column(String(300))
    corpo: Mapped[str] = mapped_column(Text)
    # Data da entrada mais recente do CHANGELOG incluída (o próximo rascunho começa depois dela)
    ate_data: Mapped[date | None] = mapped_column(Date)
    destino: Mapped[str] = mapped_column(String(12))
    # Envio a usuários e setores escolhidos: quem foi escolhido (ex.: "Ana Souza, Bia Lima; setores: Diretoria A")
    destino_descricao: Mapped[str | None] = mapped_column(Text)
    total: Mapped[int] = mapped_column(Integer, default=0)
    enviados: Mapped[int] = mapped_column(Integer, default=0)
    falhas: Mapped[int] = mapped_column(Integer, default=0)
    # Endereços que falharam, com o motivo (um por linha)
    erros: Mapped[str | None] = mapped_column(Text)
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    enviado_por_nome: Mapped[str] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
