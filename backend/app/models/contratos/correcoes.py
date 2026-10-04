# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas das correções de itens do contrato (proposta com dois olhos) e o histórico dos itens.
"""Correção de erro de cadastro dos itens do contrato (preço e quantidades).

O gestor **propõe**, outra pessoa **confirma**; só então o cadastro muda e as competências ainda abertas (medição não concluída) são
sincronizadas. `HistoricoItemContrato` guarda o antes e o depois de cada mudança, com a versão do cadastro.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson
from app.models.contratos.contrato import Contrato

SITUACOES_CORRECAO = ("pendente", "aplicada", "recusada", "cancelada")


class CorrecaoItens(Base):
    """Proposta de correção dos itens: fica pendente até outra pessoa (que não o autor) confirmar ou recusar."""

    __tablename__ = "contratos_correcoes_itens"
    __table_args__ = (CheckConstraint("situacao IN ('pendente', 'aplicada', 'recusada', 'cancelada')", name="ck_contratos_correcoes_situacao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(250))
    justificativa: Mapped[str] = mapped_column(Text)
    # [{"item_id", "descricao", "campos": {campo: {"de", "para"}}}]
    mudancas: Mapped[list[dict[str, Any]]] = mapped_column(TipoJson)
    # Prévia no momento da proposta: competências abertas afetadas e variação do valor
    previa: Mapped[dict[str, Any]] = mapped_column(TipoJson)
    situacao: Mapped[str] = mapped_column(String(12), default="pendente")
    decidido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    decidido_por_nome: Mapped[str] = mapped_column(String(250), default="")
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_decisao: Mapped[str] = mapped_column(Text, default="")
    versao_cadastro: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship()


class HistoricoItemContrato(Base):
    """Uma linha por item alterado: o que mudou, quem, quando e a versão do cadastro resultante."""

    __tablename__ = "contratos_itens_historico"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_itens.id", ondelete="SET NULL"), index=True)
    descricao_item: Mapped[str] = mapped_column(String(1000))
    versao_cadastro: Mapped[int] = mapped_column(Integer)
    correcao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_correcoes_itens.id", ondelete="SET NULL"))
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(250))
    motivo: Mapped[str] = mapped_column(Text, default="")
    # {campo: {"de", "para"}}
    campos: Mapped[dict[str, Any]] = mapped_column(TipoJson)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
