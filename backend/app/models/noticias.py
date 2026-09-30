# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do Módulo Notícias (notícias, revisões, anexos, categorias) e do portal (atalhos e configuração).
"""Módulo Notícias e portal da intranet.

- `Noticia`: a notícia, com fluxo editorial rascunho → em revisão → aprovada/devolvida (e arquivada). Fica visível no
  portal quando está aprovada e `publicar_em` já passou (o agendamento não depende de rotina). A capa guarda o
  original e as versões WebP 2:1 geradas a partir do recorte feito no editor.
- `RevisaoNoticia`: retrato de cada versão salva (histórico).
- `AnexoNoticia`: arquivos anexados (PDF, documentos, planilhas…), guardados pelo `servico_anexos`.
- `CategoriaNoticia`: categorias para filtro e identificação visual.
- `AtalhoPortal` e `ConfiguracaoPortal`: atalhos e parâmetros do slider da página inicial.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc

SITUACOES_NOTICIA = ("rascunho", "em_revisao", "aprovada", "devolvida", "arquivada")
MODOS_CAPA = ("recortar", "inteira")
CRITERIOS_SLIDER = ("automatico", "curadoria")


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class CategoriaNoticia(Base):
    """Categoria de notícia (ex.: Saúde, Integridade, Tecnologia)."""

    __tablename__ = "noticias_categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), unique=True)
    cor: Mapped[str] = mapped_column(String(7), default="#c82331")
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Noticia(Base):
    """Notícia do portal, com fluxo editorial e capa 2:1."""

    __tablename__ = "noticias"
    __table_args__ = (
        CheckConstraint(f"situacao IN ({_lista(SITUACOES_NOTICIA)})", name="ck_noticias_situacao"),
        CheckConstraint(f"capa_modo IN ({_lista(MODOS_CAPA)})", name="ck_noticias_capa_modo"),
        Index("ix_noticias_situacao_publicar", "situacao", "publicar_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Endereço público (/noticias/<slug>), gerado do título e único
    slug: Mapped[str] = mapped_column(String(240), unique=True)
    titulo: Mapped[str] = mapped_column(String(220))
    linha_fina: Mapped[str] = mapped_column(String(300), default="")
    # HTML já sanitizado no servidor (só marcação permitida)
    corpo_html: Mapped[str] = mapped_column(Text, default="")
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("noticias_categorias.id", ondelete="SET NULL"), index=True)
    situacao: Mapped[str] = mapped_column(String(12), default="rascunho")
    # Quando a notícia deve aparecer (pedido do redator; definitivo após a aprovação)
    publicar_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Depois desta data a notícia sai do slider (continua no arquivo)
    destaque_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fixada: Mapped[bool] = mapped_column(Boolean, default=False)
    # Ordem na curadoria manual do slider (nulo = fora da curadoria)
    ordem_slider: Mapped[int | None] = mapped_column(Integer)
    # Comunicado com ciência: o aviso pede ciência a cada destinatário
    exige_ciencia: Mapped[bool] = mapped_column(Boolean, default=False)
    # Público do aviso de publicação: {"usuarios_ids": [...], "setores_ids": [...]} (nulo = sem aviso)
    publico_aviso: Mapped[dict | None] = mapped_column(JSON)
    aviso_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Capa: original, recorte (x, y, largura, altura em pixels do original), modo e versões WebP {"1600": anexo_id, …}
    capa_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="SET NULL"))
    capa_recorte: Mapped[dict | None] = mapped_column(JSON)
    capa_modo: Mapped[str] = mapped_column(String(10), default="recortar")
    capa_alt: Mapped[str] = mapped_column(String(300), default="")
    capa_versoes: Mapped[dict | None] = mapped_column(JSON)
    # Autoria e aprovação (nomes guardados como retrato da época)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    autor_nome: Mapped[str] = mapped_column(String(200), default="")
    enviada_revisao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aprovado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    aprovado_por_nome: Mapped[str | None] = mapped_column(String(200))
    aprovado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_devolucao: Mapped[str | None] = mapped_column(Text)
    visualizacoes: Mapped[int] = mapped_column(Integer, default=0)
    versao: Mapped[int] = mapped_column(Integer, default=1)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    categoria: Mapped[CategoriaNoticia | None] = relationship(lazy="joined")
    anexos: Mapped[list["AnexoNoticia"]] = relationship(back_populates="noticia", cascade="all, delete-orphan", lazy="selectin",
                                                       order_by="AnexoNoticia.ordem")


class RevisaoNoticia(Base):
    """Retrato de uma versão da notícia (histórico)."""

    __tablename__ = "noticias_revisoes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    noticia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("noticias.id", ondelete="CASCADE"), index=True)
    versao: Mapped[int] = mapped_column(Integer)
    descricao: Mapped[str] = mapped_column(String(200))
    titulo: Mapped[str] = mapped_column(String(220))
    linha_fina: Mapped[str] = mapped_column(String(300), default="")
    corpo_html: Mapped[str] = mapped_column(Text, default="")
    autor_nome: Mapped[str] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class AnexoNoticia(Base):
    """Arquivo anexado à notícia."""

    __tablename__ = "noticias_anexos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    noticia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("noticias.id", ondelete="CASCADE"), index=True)
    anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="CASCADE"))
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    noticia: Mapped[Noticia] = relationship(back_populates="anexos")
    anexo: Mapped["Anexo"] = relationship(lazy="joined")  # noqa: F821


class AtalhoPortal(Base):
    """Atalho da página inicial (Outlook, Diário Oficial…)."""

    __tablename__ = "portal_atalhos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(500))
    # Imagem original e versão WebP exibida (quadrada, 480 px)
    imagem_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="SET NULL"))
    imagem_exibicao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="SET NULL"))
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    nova_aba: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class ConfiguracaoPortal(Base):
    """Parâmetros da página inicial (linha única, id = 1)."""

    __tablename__ = "portal_configuracao"
    __table_args__ = (CheckConstraint(f"criterio_slider IN ({_lista(CRITERIOS_SLIDER)})", name="ck_portal_criterio"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(String(120), default="Notícias")
    subtitulo: Mapped[str] = mapped_column(String(200), default="Comunicados, informes e atualizações institucionais.")
    quantidade_slides: Mapped[int] = mapped_column(Integer, default=4)
    segundos_por_slide: Mapped[int] = mapped_column(Integer, default=7)
    passagem_automatica: Mapped[bool] = mapped_column(Boolean, default=True)
    criterio_slider: Mapped[str] = mapped_column(String(12), default="automatico")
    titulo_sobreposto: Mapped[bool] = mapped_column(Boolean, default=True)
    quantidade_cartoes: Mapped[int] = mapped_column(Integer, default=3)
    exibir_atalhos: Mapped[bool] = mapped_column(Boolean, default=True)
    exibir_todas: Mapped[bool] = mapped_column(Boolean, default=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
    atualizado_por_nome: Mapped[str] = mapped_column(String(200), default="")
