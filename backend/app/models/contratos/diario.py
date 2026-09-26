# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do diário de bordo do contrato e das glosas ligadas às ocorrências.
"""Diário de bordo do contrato: ocorrências relatadas pela equipe e as glosas que elas implicam.

As ocorrências são registro histórico: não são editadas nem excluídas. Uma ocorrência com glosa indica
itens e quantidades a glosar; as glosas valem na competência cujo período contém a data da ocorrência e
limitam o que pode ser medido nela (saldo líquido = saldo − glosas).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson
from app.models.contratos.contrato import Contrato


class OcorrenciaDiario(Base):
    """Ocorrência relatada por um integrante da equipe, com o resultado do e-mail enviado à equipe e ao preposto."""

    __tablename__ = "contratos_diario_ocorrencias"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    # Dia em que a ocorrência aconteceu (define a competência das glosas); o registro tem data e hora próprias
    data_ocorrencia: Mapped[date] = mapped_column(Date, index=True)
    descricao: Mapped[str] = mapped_column(Text)
    possui_glosa: Mapped[bool] = mapped_column(Boolean, default=False)
    # Quem registrou (fotografia do nome e do papel no momento do registro)
    registrada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    registrada_por_nome: Mapped[str] = mapped_column(String(250))
    registrada_por_papel: Mapped[str] = mapped_column(String(40), default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    # Resultado do e-mail à equipe e ao preposto
    email_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_ok: Mapped[bool | None] = mapped_column(Boolean)
    email_destinatarios: Mapped[list[Any]] = mapped_column(TipoJson, default=list)
    email_erro: Mapped[str | None] = mapped_column(Text)

    contrato: Mapped[Contrato] = relationship(back_populates="ocorrencias")
    glosas: Mapped[list["GlosaOcorrencia"]] = relationship(
        back_populates="ocorrencia", cascade="all, delete-orphan", order_by="GlosaOcorrencia.descricao_item"
    )


class GlosaOcorrencia(Base):
    """Item e quantidade a glosar por causa de uma ocorrência."""

    __tablename__ = "contratos_diario_glosas"
    __table_args__ = (
        UniqueConstraint("ocorrencia_id", "item_id", name="contratos_diario_glosas_ocorrencia_id_item_id_key"),
        CheckConstraint("quantidade > 0", name="ck_contratos_diario_glosas_quantidade"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ocorrencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_diario_ocorrencias.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_itens.id", ondelete="CASCADE"), index=True)
    # Descrição do item no momento do registro
    descricao_item: Mapped[str] = mapped_column(String(1000))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(18, 4))

    ocorrencia: Mapped[OcorrenciaDiario] = relationship(back_populates="glosas")
