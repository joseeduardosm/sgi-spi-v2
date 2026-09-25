# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas de checklists, formulários, competências e etapas da execução.
"""Execução mensal: checklists, formulários de avaliação, competências e suas etapas.

Cada competência guarda fotografias (itens e preços, checklist, formulário) do momento em que foi
gerada, para que documentos já emitidos não mudem com alterações posteriores do contrato.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.anexo import Anexo
from app.models.auditoria import TipoJson
from app.models.contratos.contrato import Contrato, _lista_sql

# Etapas da competência, em ordem. `avaliacao` só existe quando a competência tem formulário.
ETAPAS = ("medicao", "avaliacao", "nota_fiscal", "cadin", "checklist", "consolidado", "ordem_bancaria", "concluida")
# Competência regular (período de execução) ou complementar, que paga a diferença de um reajuste retroativo
TIPOS_COMPETENCIA = ("regular", "diferenca_reajuste")


class Checklist(Base):
    """Versão do checklist de documentos mensais do contrato (etapa 5)."""

    __tablename__ = "contratos_checklists"
    __table_args__ = (UniqueConstraint("contrato_id", "versao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    versao: Mapped[int] = mapped_column(Integer)
    nome: Mapped[str] = mapped_column(String(300))
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    ativado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_por_nome: Mapped[str] = mapped_column(String(250))
    # Exclusão lógica (só versões inativas)
    excluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="checklists")
    itens: Mapped[list["ItemChecklist"]] = relationship(
        back_populates="checklist", cascade="all, delete-orphan", order_by="ItemChecklist.ordem"
    )


class ItemChecklist(Base):
    __tablename__ = "contratos_checklists_itens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    checklist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_checklists.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    nome: Mapped[str] = mapped_column(String(500))
    observacao: Mapped[str] = mapped_column(String(1000), default="")
    # Obrigatório: precisa estar anexado para concluir a etapa; opcional: pode ficar sem anexo
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    checklist: Mapped[Checklist] = relationship(back_populates="itens")


class FormularioAvaliacao(Base):
    """Versão do formulário de avaliação dos serviços (etapa 2, opcional).

    `definicao`: {"escala": [{"valor", "legenda"}], "faixas": [{"minimo", "maximo", "percentual"}],
    "grupos": [{"id", "nome", "itens": [{"id", "nome", "descricao", "peso"}]}]}.
    """

    __tablename__ = "contratos_formularios"
    __table_args__ = (UniqueConstraint("contrato_id", "versao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    versao: Mapped[int] = mapped_column(Integer)
    nome: Mapped[str] = mapped_column(String(300))
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    definicao: Mapped[dict[str, Any]] = mapped_column(TipoJson)
    ativado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_por_nome: Mapped[str] = mapped_column(String(250))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="formularios")


class ModeloGlobal(Base):
    """Modelo reutilizável (SuperRoot) de checklist ou de formulário, clonado para os contratos.

    `conteudo`: checklist → {"itens": [{"nome", "observacao"}]}; formulário → a mesma `definicao`.
    """

    __tablename__ = "contratos_modelos"
    __table_args__ = (CheckConstraint("tipo IN ('checklist', 'formulario')", name="ck_contratos_modelos_tipo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tipo: Mapped[str] = mapped_column(String(20), index=True)
    nome: Mapped[str] = mapped_column(String(300))
    conteudo: Mapped[dict[str, Any]] = mapped_column(TipoJson)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)


class Competencia(Base):
    __tablename__ = "contratos_competencias"
    __table_args__ = (
        UniqueConstraint("contrato_id", "periodo_inicio", "tipo", name="contratos_competencias_contrato_id_periodo_inicio_tipo_key"),
        CheckConstraint(f"etapa_atual IN ({_lista_sql(ETAPAS)})", name="ck_contratos_competencias_etapa"),
        CheckConstraint(f"tipo IN ({_lista_sql(TIPOS_COMPETENCIA)})", name="ck_contratos_competencias_tipo"),
        CheckConstraint("origem_valor_nf IS NULL OR origem_valor_nf IN ('medicao', 'manual')", name="ck_contratos_competencias_origem_nf"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    sequencia_vigencia: Mapped[int] = mapped_column(Integer, default=1)
    # Dia 1 do primeiro mês do período
    competencia: Mapped[date] = mapped_column(Date)
    periodo_inicio: Mapped[date] = mapped_column(Date)
    periodo_fim: Mapped[date] = mapped_column(Date)
    etapa_atual: Mapped[str] = mapped_column(String(20), default="medicao")
    tipo: Mapped[str] = mapped_column(String(30), default="regular", server_default="regular")
    # Reajuste que originou a competência de diferença (somente tipo = diferenca_reajuste)
    reajuste_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_reajustes.id", ondelete="SET NULL"), index=True)

    # Etapa 1 — medição
    medicao_iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    medicao_concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Etapa 3 — nota fiscal (principal e adicional)
    nf_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    nf_numero: Mapped[str] = mapped_column(String(100), default="")
    nf_recebida_em: Mapped[date | None] = mapped_column(Date)
    prazo_pagamento_dias: Mapped[int | None] = mapped_column(Integer)
    origem_valor_nf: Mapped[str | None] = mapped_column(String(20))
    nf_valor_bruto: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    nf_retencao_ir: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    nf_retencao_inss: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    nf_retencao_iss: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    nf_retencao_pis: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    nf_retencao_cofins: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    nf_adicional_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    nf_adicional_numero: Mapped[str] = mapped_column(String(100), default="")
    nf_adicional_valor_bruto: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    nf_adicional_retencao_ir: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    nf_adicional_retencao_inss: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    nf_adicional_retencao_iss: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    nf_adicional_retencao_pis: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    nf_adicional_retencao_cofins: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    nf_concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Etapa 6 — documento consolidado
    consolidado_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    consolidado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Etapa 7 — ordem bancária
    ob_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    ob_enviada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="competencias")
    itens: Mapped[list["ItemMedicao"]] = relationship(back_populates="competencia", cascade="all, delete-orphan", order_by="ItemMedicao.ordem")
    notas: Mapped[list["SelecaoNotaEmpenho"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="SelecaoNotaEmpenho.ordem"
    )
    ciencias: Mapped[list["CienciaMedicao"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="CienciaMedicao.registrada_em"
    )
    memorias: Mapped[list["MemoriaMedicao"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="MemoriaMedicao.versao"
    )
    consultas_cadin: Mapped[list["ConsultaCadin"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="ConsultaCadin.criado_em"
    )
    documentos: Mapped[list["DocumentoMensal"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="DocumentoMensal.ordem"
    )
    avaliacao: Mapped["AvaliacaoCompetencia | None"] = relationship(back_populates="competencia", cascade="all, delete-orphan", uselist=False)
    nf_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[nf_anexo_id])
    nf_adicional_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[nf_adicional_anexo_id])
    consolidado_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[consolidado_anexo_id])
    ob_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[ob_anexo_id])

    @property
    def parte(self) -> int | None:
        """1 ou 2 quando o mês civil se divide entre duas vigências (virada no meio do mês); senão nulo."""
        if self.tipo != "regular" or self.contrato is None:
            return None
        irmas = sorted(
            (c for c in self.contrato.competencias if c.tipo == "regular" and c.competencia == self.competencia),
            key=lambda c: c.periodo_inicio,
        )
        return irmas.index(self) + 1 if len(irmas) > 1 and self in irmas else None

    @property
    def identificador(self) -> str:
        """Chave da rota da tela: `AAAA-MM`, `AAAA-MM-1`/`AAAA-MM-2` (mês dividido) ou `AAAA-MM-dif` (diferença de reajuste)."""
        if self.tipo == "diferenca_reajuste":
            return f"{self.competencia:%Y-%m}-dif"
        return f"{self.competencia:%Y-%m}" + (f"-{self.parte}" if self.parte else "")

    @property
    def numero_competencia(self) -> str:
        """Rótulo exibido: `01/2027`, `01/2027 · 1ª parte` ou `Diferença de reajuste 01/2026 a 04/2026`."""
        if self.tipo == "diferenca_reajuste":
            return f"Diferença de reajuste {self.periodo_inicio:%m/%Y} a {self.periodo_fim:%m/%Y}"
        return f"{self.competencia:%m/%Y}" + (f" · {self.parte}ª parte" if self.parte else "")


class ItemMedicao(Base):
    """Fotografia do item do contrato na competência, com a quantidade prevista e a medida."""

    __tablename__ = "contratos_competencias_itens"
    __table_args__ = (UniqueConstraint("competencia_id", "item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_itens.id", ondelete="SET NULL"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    descricao: Mapped[str] = mapped_column(String(1000))
    tipo: Mapped[str] = mapped_column(String(20))
    calcula_pro_rata: Mapped[bool] = mapped_column(Boolean, default=True)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    # Meses equivalentes do período (ex.: 0,5333 em mês parcial com pró-rata)
    fator_meses: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal(1))
    quantidade_prevista: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    quantidade_medida: Mapped[Decimal] = mapped_column(Numeric(18, 10), default=Decimal(0))

    competencia: Mapped[Competencia] = relationship(back_populates="itens")


class SelecaoNotaEmpenho(Base):
    """NEs escolhidas na medição, em ordem de consumo: o débito esgota a 1ª antes de passar à 2ª."""

    __tablename__ = "contratos_competencias_notas"

    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), primary_key=True)
    # A exclusão da NE ligada a competência é barrada pelo serviço; o CASCADE permite excluir o contrato inteiro
    nota_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_notas_empenho.id", ondelete="CASCADE"), primary_key=True, index=True)
    ordem: Mapped[int] = mapped_column(Integer)

    competencia: Mapped[Competencia] = relationship(back_populates="notas")


class CienciaMedicao(Base):
    """Ciência de um integrante da equipe na medição (mínimo de 2 pessoas diferentes)."""

    __tablename__ = "contratos_competencias_ciencias"
    __table_args__ = (UniqueConstraint("competencia_id", "usuario_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    nome: Mapped[str] = mapped_column(String(250))
    papel: Mapped[str] = mapped_column(String(40))
    registrada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    competencia: Mapped[Competencia] = relationship(back_populates="ciencias")


class MemoriaMedicao(Base):
    """Memória de cálculo em PDF. Nova versão só quando os dados (hash) mudam."""

    __tablename__ = "contratos_competencias_memorias"
    __table_args__ = (UniqueConstraint("competencia_id", "versao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    versao: Mapped[int] = mapped_column(Integer)
    anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    competencia: Mapped[Competencia] = relationship(back_populates="memorias")
    anexo: Mapped[Anexo] = relationship()


class ConsultaCadin(Base):
    """Consulta ao CADIN. Com pendência, a etapa continua aberta; sem pendência, conclui."""

    __tablename__ = "contratos_competencias_cadin"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    possui_pendencia: Mapped[bool] = mapped_column(Boolean)
    pendencia: Mapped[str] = mapped_column(String(2000), default="")
    texto_notificacao: Mapped[str] = mapped_column(String(2500), default="")
    certidao_anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    email_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_por_nome: Mapped[str] = mapped_column(String(250))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    competencia: Mapped[Competencia] = relationship(back_populates="consultas_cadin")
    certidao_anexo: Mapped[Anexo] = relationship(foreign_keys=[certidao_anexo_id])
    email_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[email_anexo_id])


class DocumentoMensal(Base):
    """Documento do checklist copiado para a competência (um PDF por documento)."""

    __tablename__ = "contratos_competencias_documentos"
    __table_args__ = (UniqueConstraint("competencia_id", "ordem"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    # Versão do checklist de origem (sem FK: a versão pode ser excluída logicamente depois)
    checklist_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    ordem: Mapped[int] = mapped_column(Integer)
    nome: Mapped[str] = mapped_column(String(500))
    observacao: Mapped[str] = mapped_column(String(1000), default="")
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))

    competencia: Mapped[Competencia] = relationship(back_populates="documentos")
    anexo: Mapped[Anexo | None] = relationship()


class AvaliacaoCompetencia(Base):
    """Avaliação dos serviços na competência (etapa 2), com a fotografia do formulário.

    Respostas: [{"item_id", "nota", "justificativa"}]. Assinaturas do ateste:
    [{"papel", "usuario_id", "nome", "ciencia_em"}].
    """

    __tablename__ = "contratos_competencias_avaliacoes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), unique=True)
    formulario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    definicao: Mapped[dict[str, Any]] = mapped_column(TipoJson)
    respostas_iniciais: Mapped[list[Any]] = mapped_column(TipoJson, default=list)
    avaliador_inicial_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    avaliacao_inicial_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    respostas_gestor: Mapped[list[Any]] = mapped_column(TipoJson, default=list)
    complemento_gestor: Mapped[str] = mapped_column(String(4000), default="")
    gestor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    avaliacao_gestor_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assinaturas: Mapped[list[Any]] = mapped_column(TipoJson, default=list)
    assinaturas_definidas_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pdf_gerado_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    pdf_assinado_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconsideracoes: Mapped[int] = mapped_column(Integer, default=0)
    reconsideracao_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))

    competencia: Mapped[Competencia] = relationship(back_populates="avaliacao")
    pdf_gerado_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[pdf_gerado_anexo_id])
    pdf_assinado_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[pdf_assinado_anexo_id])
    reconsideracao_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[reconsideracao_anexo_id])
