# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do módulo Contratações (ETP e TR): documentos, árvore de itens, revisões e versões.
"""Módulo Contratações: Estudo Técnico Preliminar (ETP) e Termo de Referência (TR).

- `DocumentoContratacao`: raiz do ETP ou TR (situação, processo SEI, vínculo opcional com um contrato).
- `SecaoContratacao` e `ItemContratacao`: o conteúdo em árvore (item, subitem, inciso, alínea, subseção). `conteudo_html` é a fonte da
  verdade (sanitizado); `conteudo` é sempre a projeção em texto. `secao_id` também é gravado em toda a subárvore.
- `LinhaTabelaTr`: tabela estruturada do item 1.1 do TR. `RevisaoItem`: comentário ou proposta de alteração.
- `MembroDocumento`: quem compartilha o documento (editor ou revisor).
- **Versionamento (estilo BookStack):** `VersaoDocumento` guarda a *foto* da árvore em marcos (criação, importação, situação,
  proposta, manual, restauração…) e `HistoricoItem` guarda cada edição de um item (antes e depois).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson

TIPOS_DOCUMENTO = ("etp", "tr")
SITUACOES = ("rascunho", "em_revisao", "concluido")
TIPOS_ITEM = ("item", "subitem", "inciso", "alinea", "subsecao")
PAPEIS = ("editor", "revisor")
TIPOS_VERSAO = ("criacao", "manual", "importacao", "situacao", "proposta", "restauracao", "migracao", "sessao")
MUDANCAS = ("criou", "editou", "moveu", "removeu", "restaurou")


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class DocumentoContratacao(Base):
    """ETP ou TR."""
    __tablename__ = "contratacoes_documentos"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista(TIPOS_DOCUMENTO)})", name="ck_contratacoes_documentos_tipo"),
        CheckConstraint(f"situacao IN ({_lista(SITUACOES)})", name="ck_contratacoes_documentos_situacao"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tipo: Mapped[str] = mapped_column(String(3))
    nome: Mapped[str] = mapped_column(String(300))
    processo: Mapped[str] = mapped_column(String(100), default="")
    link_sei: Mapped[str | None] = mapped_column(String(500))
    situacao: Mapped[str] = mapped_column(String(12), default="rascunho")
    criador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    atualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    contrato_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos.id", ondelete="SET NULL"), index=True)
    origem_sgi_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
    # Última edição de conteúdo (base da versão automática "antes da sessão")
    ultima_edicao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    secoes: Mapped[list["SecaoContratacao"]] = relationship(back_populates="documento", cascade="all, delete-orphan", order_by="SecaoContratacao.ordem")
    membros: Mapped[list["MembroDocumento"]] = relationship(back_populates="documento", cascade="all, delete-orphan")
    versoes: Mapped[list["VersaoDocumento"]] = relationship(back_populates="documento", cascade="all, delete-orphan", order_by="VersaoDocumento.numero")


class SecaoContratacao(Base):
    __tablename__ = "contratacoes_secoes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratacoes_documentos.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    titulo: Mapped[str] = mapped_column(String(300), default="")
    origem_sgi_id: Mapped[str | None] = mapped_column(String(40), unique=True)

    documento: Mapped[DocumentoContratacao] = relationship(back_populates="secoes")
    itens: Mapped[list["ItemContratacao"]] = relationship(back_populates="secao", cascade="all, delete-orphan", order_by="ItemContratacao.ordem")


class ItemContratacao(Base):
    """Nó da árvore. `pai_id` define a hierarquia; `secao_id` fica também nos descendentes (consulta rápida)."""
    __tablename__ = "contratacoes_itens"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista(TIPOS_ITEM)})", name="ck_contratacoes_itens_tipo"),
        Index("ix_contratacoes_itens_secao_pai_ordem", "secao_id", "pai_id", "ordem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    secao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratacoes_secoes.id", ondelete="CASCADE"), index=True)
    pai_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratacoes_itens.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(10), default="item")
    ordem: Mapped[int] = mapped_column(Integer, default=1)
    conteudo: Mapped[str] = mapped_column(Text, default="")
    conteudo_html: Mapped[str | None] = mapped_column(Text)
    precisa_revisao: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    origem_sgi_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    secao: Mapped[SecaoContratacao] = relationship(back_populates="itens")
    filhos: Mapped[list["ItemContratacao"]] = relationship(cascade="all, delete-orphan", order_by="ItemContratacao.ordem", back_populates="pai")
    pai: Mapped["ItemContratacao | None"] = relationship(back_populates="filhos", remote_side="ItemContratacao.id")
    linhas_tabela: Mapped[list["LinhaTabelaTr"]] = relationship(back_populates="item", cascade="all, delete-orphan", order_by="LinhaTabelaTr.ordem")
    revisoes: Mapped[list["RevisaoItem"]] = relationship(back_populates="item", cascade="all, delete-orphan", order_by="RevisaoItem.criada_em")
    comentarios_importados: Mapped[list["ComentarioImportado"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class LinhaTabelaTr(Base):
    """Linha da tabela do item 1.1 do TR (itens precificáveis)."""
    __tablename__ = "contratacoes_tabela_tr"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratacoes_itens.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    descricao: Mapped[str] = mapped_column(Text, default="")
    siafisico: Mapped[str] = mapped_column(String(60), default="")
    catser_catmat: Mapped[str] = mapped_column(String(60), default="")
    unidade: Mapped[str] = mapped_column(String(60), default="")
    quantidade_mensal: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    quantidade_objeto: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal(0))
    origem_sgi_id: Mapped[str | None] = mapped_column(String(40), unique=True)

    item: Mapped[ItemContratacao] = relationship(back_populates="linhas_tabela")


class RevisaoItem(Base):
    """Comentário ou proposta de alteração de um item. A proposta aplicada fica registrada (quem e quando)."""
    __tablename__ = "contratacoes_revisoes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratacoes_itens.id", ondelete="CASCADE"), index=True)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(200), default="")
    comentario: Mapped[str] = mapped_column(Text, default="")
    conteudo_original: Mapped[str] = mapped_column(Text, default="")
    conteudo_original_html: Mapped[str | None] = mapped_column(Text)
    conteudo_proposto: Mapped[str | None] = mapped_column(Text)
    conteudo_proposto_html: Mapped[str | None] = mapped_column(Text)
    aplicada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aplicada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    aplicada_por_nome: Mapped[str | None] = mapped_column(String(200))
    resolvida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolvida_por_nome: Mapped[str | None] = mapped_column(String(200))
    origem_sgi_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    item: Mapped[ItemContratacao] = relationship(back_populates="revisoes")


class ComentarioImportado(Base):
    """Comentário do Word trazido na importação (somente leitura: o autor externo pode não ter conta)."""
    __tablename__ = "contratacoes_comentarios_importados"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratacoes_itens.id", ondelete="CASCADE"), index=True)
    id_externo: Mapped[str] = mapped_column(String(60), default="")
    autor: Mapped[str] = mapped_column(String(200), default="")
    iniciais: Mapped[str | None] = mapped_column(String(20))
    comentado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comentario: Mapped[str] = mapped_column(Text, default="")
    trecho: Mapped[str] = mapped_column(Text, default="")
    abrange_mais: Mapped[bool] = mapped_column(Boolean, default=False)
    origem_sgi_id: Mapped[str | None] = mapped_column(String(40), unique=True)

    item: Mapped[ItemContratacao] = relationship(back_populates="comentarios_importados")


class MembroDocumento(Base):
    """Compartilhamento do documento: `editor` edita; `revisor` só comenta e propõe."""
    __tablename__ = "contratacoes_membros"
    __table_args__ = (
        UniqueConstraint("documento_id", "usuario_id", name="uq_contratacoes_membros_documento_usuario"),
        CheckConstraint(f"papel IN ({_lista(PAPEIS)})", name="ck_contratacoes_membros_papel"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratacoes_documentos.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    papel: Mapped[str] = mapped_column(String(8), default="editor")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    documento: Mapped[DocumentoContratacao] = relationship(back_populates="membros")


class VersaoDocumento(Base):
    """Marco do documento: a foto da árvore naquele momento (como a revisão de uma página do BookStack)."""
    __tablename__ = "contratacoes_versoes"
    __table_args__ = (
        UniqueConstraint("documento_id", "numero", name="uq_contratacoes_versoes_documento_numero"),
        CheckConstraint(f"tipo IN ({_lista(TIPOS_VERSAO)})", name="ck_contratacoes_versoes_tipo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratacoes_documentos.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(12))
    resumo: Mapped[str] = mapped_column(String(500), default="")
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(200), default="")
    # Retrato do documento: {"nome", "processo", "situacao", "secoes": [...], "itens": [...], "linhas_tabela": [...]}
    foto: Mapped[dict] = mapped_column(TipoJson)
    hash: Mapped[str] = mapped_column(String(64), default="")
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    documento: Mapped[DocumentoContratacao] = relationship(back_populates="versoes")


class HistoricoItem(Base):
    """Uma edição de um item (antes e depois). Não tem chave estrangeira para o item: o histórico sobrevive à exclusão dele."""
    __tablename__ = "contratacoes_historico_itens"
    __table_args__ = (
        CheckConstraint(f"mudanca IN ({_lista(MUDANCAS)})", name="ck_contratacoes_historico_mudanca"),
        Index("ix_contratacoes_historico_item_em", "item_id", "ocorrido_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratacoes_documentos.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    mudanca: Mapped[str] = mapped_column(String(10))
    antes_html: Mapped[str | None] = mapped_column(Text)
    depois_html: Mapped[str | None] = mapped_column(Text)
    detalhe: Mapped[str] = mapped_column(String(300), default="")
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(200), default="")
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
