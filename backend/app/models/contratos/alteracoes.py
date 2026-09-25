# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas de prorrogação, reajuste e aditamento/supressão.
"""Alterações do contrato: prorrogação de vigência, reajuste de preços e aditamento/supressão.

Cada processo em andamento é um rascunho; somente a conclusão aplica o efeito ao contrato.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.anexo import Anexo
from app.models.auditoria import TipoJson
from app.models.contratos.contrato import Contrato


# ---------------------------------------------------------------------------------------------
# Prorrogação
# ---------------------------------------------------------------------------------------------

class Prorrogacao(Base):
    """Termo aditivo registrado: fotografia imutável da nova vigência."""

    __tablename__ = "contratos_prorrogacoes"
    __table_args__ = (UniqueConstraint("contrato_id", "data_inicio"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    meses: Mapped[int] = mapped_column(Integer)
    assinada_em: Mapped[date] = mapped_column(Date)
    numero_termo: Mapped[str] = mapped_column(String(100), default="")
    fim_anterior: Mapped[date] = mapped_column(Date)
    data_inicio: Mapped[date] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)
    anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    # Código do documento importante criado para o termo (024, 025…)
    codigo_documento: Mapped[int | None] = mapped_column(Integer)
    relatorio_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="prorrogacoes")
    anexo: Mapped[Anexo] = relationship(foreign_keys=[anexo_id])
    relatorio_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[relatorio_anexo_id])


class ProcessoProrrogacao(Base):
    """Rascunho da prorrogação (tela 4): prazo, itens sob demanda, parecer e ciências.

    `plano_sob_demanda`: [{"item_id", "limite", "apontamentos": {"AAAA-MM-01": quantidade}}].
    """

    __tablename__ = "contratos_prorrogacoes_processos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    situacao: Mapped[str] = mapped_column(String(20), default="rascunho")
    meses: Mapped[int | None] = mapped_column(Integer)
    regra_sob_demanda: Mapped[str] = mapped_column(String(30), default="saldo_remanescente")
    plano_sob_demanda: Mapped[list[Any]] = mapped_column(TipoJson, default=list)
    avaliacao_geral: Mapped[str] = mapped_column(Text, default="")
    resumo_qualidade: Mapped[str] = mapped_column(Text, default="")
    historico_ocorrencias: Mapped[str] = mapped_column(Text, default="")
    reclamacoes: Mapped[str] = mapped_column(Text, default="")
    atendimento_chamados: Mapped[str] = mapped_column(Text, default="")
    parecer: Mapped[str] = mapped_column(Text, default="")
    relatorio_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    relatorio_hash: Mapped[str] = mapped_column(String(64), default="")
    prorrogacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_prorrogacoes.id", ondelete="SET NULL"))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    ciencias: Mapped[list["CienciaProrrogacao"]] = relationship(
        back_populates="processo", cascade="all, delete-orphan", order_by="CienciaProrrogacao.registrada_em"
    )
    relatorio_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[relatorio_anexo_id])


# Um rascunho por contrato
Index(
    "ux_contratos_prorrogacoes_processos_rascunho",
    ProcessoProrrogacao.contrato_id,
    unique=True,
    postgresql_where=text("situacao = 'rascunho'"),
    sqlite_where=text("situacao = 'rascunho'"),
)


class CienciaProrrogacao(Base):
    __tablename__ = "contratos_prorrogacoes_ciencias"
    __table_args__ = (UniqueConstraint("processo_id", "usuario_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    processo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_prorrogacoes_processos.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    nome: Mapped[str] = mapped_column(String(250))
    papel: Mapped[str] = mapped_column(String(40))
    registrada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    processo: Mapped[ProcessoProrrogacao] = relationship(back_populates="ciencias")


# ---------------------------------------------------------------------------------------------
# Reajuste
# ---------------------------------------------------------------------------------------------

class Reajuste(Base):
    __tablename__ = "contratos_reajustes"
    __table_args__ = (CheckConstraint("situacao IN ('rascunho', 'concluido', 'cancelado')", name="ck_contratos_reajustes_situacao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    sequencia_vigencia: Mapped[int] = mapped_column(Integer)
    vigencia_inicio: Mapped[date] = mapped_column(Date)
    vigencia_fim: Mapped[date] = mapped_column(Date)
    # Primeiro mês com os novos preços (dia 1)
    mes_referencia: Mapped[date] = mapped_column(Date)
    situacao: Mapped[str] = mapped_column(String(20), default="rascunho")
    base_atual: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    base_reajustada: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    valor_global_atual: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    valor_global_reajustado: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    evidencia_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    apostilamento_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="reajustes")
    itens: Mapped[list["ItemReajuste"]] = relationship(back_populates="reajuste", cascade="all, delete-orphan", order_by="ItemReajuste.ordem")
    memorias: Mapped[list["MemoriaReajuste"]] = relationship(
        back_populates="reajuste", cascade="all, delete-orphan", order_by="MemoriaReajuste.versao"
    )
    evidencia_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[evidencia_anexo_id])
    apostilamento_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[apostilamento_anexo_id])


Index(
    "ux_contratos_reajustes_rascunho",
    Reajuste.contrato_id,
    unique=True,
    postgresql_where=text("situacao = 'rascunho'"),
    sqlite_where=text("situacao = 'rascunho'"),
)


class ItemReajuste(Base):
    __tablename__ = "contratos_reajustes_itens"
    __table_args__ = (UniqueConstraint("reajuste_id", "item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reajuste_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_reajustes.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_itens.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    descricao: Mapped[str] = mapped_column(String(1000))
    tipo: Mapped[str] = mapped_column(String(20))
    quantidade_mensal: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    valor_unitario_atual: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    # Em pontos percentuais: 2 = 2%
    indice_percentual: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal(0))
    # Teto opcional do preço reajustado
    valor_referencial: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_unitario_reajustado: Mapped[Decimal] = mapped_column(Numeric(18, 2))

    reajuste: Mapped[Reajuste] = relationship(back_populates="itens")


class MemoriaReajuste(Base):
    __tablename__ = "contratos_reajustes_memorias"
    __table_args__ = (UniqueConstraint("reajuste_id", "versao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reajuste_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_reajustes.id", ondelete="CASCADE"), index=True)
    versao: Mapped[int] = mapped_column(Integer)
    pdf_anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    xlsx_anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    reajuste: Mapped[Reajuste] = relationship(back_populates="memorias")
    pdf_anexo: Mapped[Anexo] = relationship(foreign_keys=[pdf_anexo_id])
    xlsx_anexo: Mapped[Anexo] = relationship(foreign_keys=[xlsx_anexo_id])


# ---------------------------------------------------------------------------------------------
# Aditamento / supressão
# ---------------------------------------------------------------------------------------------

class AlteracaoQuantidade(Base):
    __tablename__ = "contratos_alteracoes"
    __table_args__ = (
        CheckConstraint("tipo IN ('aditamento', 'supressao')", name="ck_contratos_alteracoes_tipo"),
        CheckConstraint(
            "situacao IN ('rascunho', 'aguardando_ciencias', 'concluida', 'cancelada')", name="ck_contratos_alteracoes_situacao"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    situacao: Mapped[str] = mapped_column(String(30), default="rascunho")
    sequencia_vigencia: Mapped[int] = mapped_column(Integer)
    vigencia_inicio: Mapped[date] = mapped_column(Date)
    vigencia_fim: Mapped[date] = mapped_column(Date)
    # Primeiro mês com as novas quantidades (dia 1)
    mes_efeito: Mapped[date] = mapped_column(Date)
    valor_global_original: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    impacto_valor: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    # Em pontos percentuais sobre o valor original da vigência
    impacto_percentual: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=Decimal(0))
    justificativa_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    autorizacao_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    de_acordo_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    termo_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    memoria_pdf_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    memoria_xlsx_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    consolidado_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="alteracoes")
    itens: Mapped[list["ItemAlteracao"]] = relationship(back_populates="alteracao", cascade="all, delete-orphan", order_by="ItemAlteracao.ordem")
    ciencias: Mapped[list["CienciaAlteracao"]] = relationship(
        back_populates="alteracao", cascade="all, delete-orphan", order_by="CienciaAlteracao.registrada_em"
    )


Index(
    "ux_contratos_alteracoes_em_andamento",
    AlteracaoQuantidade.contrato_id,
    unique=True,
    postgresql_where=text("situacao IN ('rascunho', 'aguardando_ciencias')"),
    sqlite_where=text("situacao IN ('rascunho', 'aguardando_ciencias')"),
)


class ItemAlteracao(Base):
    __tablename__ = "contratos_alteracoes_itens"
    __table_args__ = (UniqueConstraint("alteracao_id", "item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    alteracao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_alteracoes.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_itens.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    descricao: Mapped[str] = mapped_column(String(1000))
    tipo: Mapped[str] = mapped_column(String(20))
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    # Contínuo: quantidade mensal; sob demanda: limite da vigência
    quantidade_original: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    quantidade_nova: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    quantidade_executada: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    impacto_valor: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))

    alteracao: Mapped[AlteracaoQuantidade] = relationship(back_populates="itens")


class CienciaAlteracao(Base):
    __tablename__ = "contratos_alteracoes_ciencias"
    __table_args__ = (UniqueConstraint("alteracao_id", "usuario_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    alteracao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_alteracoes.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    nome: Mapped[str] = mapped_column(String(250))
    papel: Mapped[str] = mapped_column(String(40))
    registrada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    alteracao: Mapped[AlteracaoQuantidade] = relationship(back_populates="ciencias")
