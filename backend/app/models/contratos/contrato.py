# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do contrato, itens, equipe e documentos importantes.
"""Contrato, itens financeiros, equipe de gestão/fiscalização e documentos importantes.

Totais (base mensal, valor global, situação) não são gravados: são calculados a partir dos
itens e das datas em `services/contratos/calculos.py`, para nunca divergirem.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.anexo import Anexo
from app.models.contratos.empresa import EmpresaContratada

# Os seis papéis da equipe têm os mesmos poderes dentro do contrato
PAPEIS_EQUIPE = (
    "gestor",
    "gestor_suplente",
    "fiscal_administrativo",
    "fiscal_administrativo_suplente",
    "fiscal_tecnico",
    "fiscal_tecnico_suplente",
)
# Periodicidades aceitas para as competências, em meses (mensal, bimestral, trimestral, semestral, anual)
PERIODICIDADES = (1, 2, 3, 6, 12)
# Situações possíveis do contrato (normalmente calculadas pelas datas)
SITUACOES = ("ativo", "a_vencer", "encerrado", "suspenso")
# "continuo": quantidade fixa todo mês; "sob_demanda": consumo variável até um teto
TIPOS_ITEM = ("continuo", "sob_demanda")


def _lista_sql(valores: tuple) -> str:
    """Monta a lista usada nos CHECKs do banco a partir das tuplas acima (ex.: `'a', 'b'` ou `1, 2`)."""
    return ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in valores)


class Contrato(Base):
    """Contrato administrativo: cabeçalho, prazos, processos SEI e ligações com todo o módulo."""
    __tablename__ = "contratos"
    # Regras garantidas também pelo próprio banco (e não só pela aplicação)
    __table_args__ = (
        UniqueConstraint("sequencial", "ano"),
        CheckConstraint(f"periodicidade_meses IN ({_lista_sql(PERIODICIDADES)})", name="ck_contratos_periodicidade"),
        CheckConstraint("mes_reajuste BETWEEN 1 AND 12", name="ck_contratos_mes_reajuste"),
        CheckConstraint("vigencia_inicial_meses > 0", name="ck_contratos_vigencia_inicial"),
        CheckConstraint("vigencia_maxima_meses >= vigencia_inicial_meses", name="ck_contratos_vigencia_maxima"),
        CheckConstraint(
            f"situacao_forcada IS NULL OR situacao_forcada IN ({_lista_sql(SITUACOES)})", name="ck_contratos_situacao_forcada"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Número exibido como NNN/AAAA (ex.: 012/2026)
    sequencial: Mapped[int] = mapped_column(Integer)
    ano: Mapped[int] = mapped_column(Integer)
    # RESTRICT: não se exclui uma empresa que tenha contratos
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_empresas.id", ondelete="RESTRICT"), index=True)
    # Nome curto para identificar o contrato nas listas, e a descrição completa do objeto
    apelido: Mapped[str] = mapped_column(String(200), default="")
    objeto: Mapped[str] = mapped_column(String(4000))
    data_inicio: Mapped[date] = mapped_column(Date)
    # Fim da vigência atual (avança a cada prorrogação)
    data_fim: Mapped[date] = mapped_column(Date)
    # Prazo da vigência original e o prazo máximo permitido com as prorrogações, em meses
    vigencia_inicial_meses: Mapped[int] = mapped_column(Integer)
    vigencia_maxima_meses: Mapped[int] = mapped_column(Integer)
    periodicidade_meses: Mapped[int] = mapped_column(Integer, default=1)
    # Mês do ano em que o contrato pode ser reajustado
    mes_reajuste: Mapped[int] = mapped_column(Integer)
    # Processos SEI de gestão e de execução (número e link)
    sei_gestao_numero: Mapped[str] = mapped_column(String(100))
    sei_gestao_link: Mapped[str] = mapped_column(String(1000))
    sei_execucao_numero: Mapped[str] = mapped_column(String(100))
    sei_execucao_link: Mapped[str] = mapped_column(String(1000))
    # Nulo = situação calculada pelas datas
    situacao_forcada: Mapped[str | None] = mapped_column(String(20))
    # Fotografia do valor global depois de um reajuste (MVP 6)
    valor_global_reajustado: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    criador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Controle de concorrência: cada gravação incrementa; quem salvou uma versão antiga recebe 409
    versao: Mapped[int] = mapped_column(Integer, default=1)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    # Relacionamentos: tudo o que pertence ao contrato é apagado junto com ele (`delete-orphan`).
    # Os nomes entre aspas são resolvidos depois, quando os outros arquivos de modelos são carregados.
    empresa: Mapped[EmpresaContratada] = relationship()
    itens: Mapped[list["ItemContrato"]] = relationship(
        back_populates="contrato", cascade="all, delete-orphan", order_by="ItemContrato.ordem"
    )
    equipe: Mapped[list["DesignacaoEquipe"]] = relationship(back_populates="contrato", cascade="all, delete-orphan")
    documentos: Mapped[list["DocumentoContrato"]] = relationship(
        back_populates="contrato", cascade="all, delete-orphan", order_by="DocumentoContrato.codigo_tipo"
    )
    previsoes: Mapped[list["PrevisaoVigencia"]] = relationship(back_populates="contrato", cascade="all, delete-orphan")  # noqa: F821
    notas_empenho: Mapped[list["NotaEmpenho"]] = relationship(  # noqa: F821
        back_populates="contrato", cascade="all, delete-orphan", order_by="NotaEmpenho.criado_em"
    )
    checklists: Mapped[list["Checklist"]] = relationship(  # noqa: F821
        back_populates="contrato", cascade="all, delete-orphan", order_by="Checklist.versao"
    )
    formularios: Mapped[list["FormularioAvaliacao"]] = relationship(  # noqa: F821
        back_populates="contrato", cascade="all, delete-orphan", order_by="FormularioAvaliacao.versao"
    )
    competencias: Mapped[list["Competencia"]] = relationship(  # noqa: F821
        back_populates="contrato", cascade="all, delete-orphan", order_by="Competencia.periodo_inicio"
    )
    prorrogacoes: Mapped[list["Prorrogacao"]] = relationship(  # noqa: F821
        back_populates="contrato", cascade="all, delete-orphan", order_by="Prorrogacao.data_inicio"
    )
    reajustes: Mapped[list["Reajuste"]] = relationship(  # noqa: F821
        back_populates="contrato", cascade="all, delete-orphan", order_by="Reajuste.criado_em"
    )
    alteracoes: Mapped[list["AlteracaoQuantidade"]] = relationship(  # noqa: F821
        back_populates="contrato", cascade="all, delete-orphan", order_by="AlteracaoQuantidade.criado_em"
    )

    @property
    def numero(self) -> str:
        """Número no formato exibido nas telas (ex.: `012/2026`)."""
        return f"{self.sequencial:03d}/{self.ano:04d}"


class ItemContrato(Base):
    """Item financeiro do contrato (serviço ou material, com quantidade e preço unitário)."""
    __tablename__ = "contratos_itens"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista_sql(TIPOS_ITEM)})", name="ck_contratos_itens_tipo"),
        CheckConstraint("valor_unitario >= 0", name="ck_contratos_itens_valor_unitario"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    # Posição do item na lista (1, 2, 3…). Sem índice único para permitir reordenar em uma gravação.
    ordem: Mapped[int] = mapped_column(Integer)
    descricao: Mapped[str] = mapped_column(String(1000))
    tipo: Mapped[str] = mapped_column(String(20))
    # Faturamento: com pró-rata (proporcional em mês parcial) ou sempre integral
    calcula_pro_rata: Mapped[bool] = mapped_column(Boolean, default=True)
    # Códigos de classificação orçamentária e de catálogo (opcionais)
    codigo_classe: Mapped[str] = mapped_column(String(80), default="")
    codigo_natureza_despesa: Mapped[str] = mapped_column(String(80), default="")
    codigo_siafisico: Mapped[str] = mapped_column(String(80), default="")
    codigo_catmat_catser: Mapped[str] = mapped_column(String(80), default="")
    # Contínuo: quantidade de todo mês
    quantidade_mensal: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    # Sob demanda: teto da vigência inicial. Contínuo: não usado (mensal × meses)
    quantidade_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    # Soma das medições concluídas (MVP 3)
    quantidade_executada: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="itens")


class DesignacaoEquipe(Base):
    """Designação de um usuário do portal para um papel. A troca encerra a anterior (`valido_ate`)."""

    __tablename__ = "contratos_equipe"
    __table_args__ = (
        UniqueConstraint("contrato_id", "usuario_id", "papel"),
        CheckConstraint(f"papel IN ({_lista_sql(PAPEIS_EQUIPE)})", name="ck_contratos_equipe_papel"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True)
    papel: Mapped[str] = mapped_column(String(40))
    # Nome no momento da designação (fotografia usada em ciências e documentos)
    nome_usuario: Mapped[str] = mapped_column(String(250))
    valido_de: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valido_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="equipe")
# Documento de um tipo do catálogo por contrato; enviar de novo substitui o anexo


class DocumentoContrato(Base):
    """Documento importante anexado (catálogo 001–023; 024+ = termos aditivos de prorrogação)."""

    __tablename__ = "contratos_documentos"
    __table_args__ = (UniqueConstraint("contrato_id", "codigo_tipo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    codigo_tipo: Mapped[int] = mapped_column(Integer)
    # Nome do documento conforme o catálogo (`catalogo_documentos.py`)
    titulo: Mapped[str] = mapped_column(String(300))
    anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="SET NULL"), index=True)
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="documentos")
    anexo: Mapped[Anexo | None] = relationship()
