# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela dos rascunhos compartilhados dos formulários do contrato (diário, avaliação e medição).
"""Rascunho salvo no servidor: um por tela (`tipo` + `chave`) e por contrato, visível a quem acessa Contratos e editável por quem edita o contrato."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson

TIPOS_RASCUNHO = ("diario", "avaliacao", "medicao")


class RascunhoContrato(Base):
    """Campos digitados e ainda não registrados, guardados para a equipe continuar (a gravação por cima exige a versão que a pessoa viu)."""

    __tablename__ = "contratos_rascunhos"
    __table_args__ = (
        UniqueConstraint("contrato_id", "tipo", "chave", name="uq_contratos_rascunhos_tela"),
        CheckConstraint("tipo IN ('diario', 'avaliacao', 'medicao')", name="ck_contratos_rascunhos_tipo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    # Tela do rascunho e, nas telas por competência (avaliação, medição), o id da competência; no diário, vazio
    tipo: Mapped[str] = mapped_column(String(20))
    chave: Mapped[str] = mapped_column(String(60), default="")
    dados: Mapped[dict[str, Any]] = mapped_column(TipoJson)
    # Sobe a cada gravação: quem grava informa a que viu, para não apagar sem querer o que outra pessoa salvou
    versao: Mapped[int] = mapped_column(Integer, default=1)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    atualizado_por_nome: Mapped[str] = mapped_column(String(250))
