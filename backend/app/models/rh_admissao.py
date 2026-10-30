# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas da admissão: modelos editáveis (resolução, e-mail, termo de posse, boas-vindas), checklists de documentos e a trilha da admissão.
"""Admissão do RH (Fase 3).

- `ModeloRh`: máscara editável de um texto do RH (HTML com placeholders `#nome` de lista fechada). Tipos: `resolucao_nomeacao`, `email_nomeacao_publicada`, `termo_posse`, `boas_vindas`.
- `ChecklistRh`, `ItemChecklistRh` e `ChecklistClassificacao`: documentos exigidos na admissão, por **classificação do cargo** (grupo 1 ou 2 + nível 1 a 18, ex.: 1.15, 1.16, 1.17),
  uma ou várias por checklist; `aplica_a_outros` cobre os cargos sem classificação (tipo OUTRO).
- `Admissao`: a trilha de uma pessoa (uma por ficha): chamado no GLPI → documentos → resolução → número no Protocolo → publicação (o e-mail de nomeação sai sozinho) → posse → entrada no SGI.
- `AdmissaoDocumento`: andamento de cada documento do checklist (envio ao Portal de Indicações, sistema externo: aqui só se registra o envio e o comprovante).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.anexo import Anexo

TIPOS_MODELO = ("resolucao_nomeacao", "email_nomeacao_publicada", "termo_posse", "boas_vindas")
# Etapas da trilha, na ordem; `concluida` fecha a admissão
ETAPAS = ("chamado", "documentos", "resolucao", "protocolo", "publicacao", "posse", "concluida")


class ModeloRh(Base):
    """Texto editável do RH (um por tipo)."""
    __tablename__ = "rh_modelos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(40), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    assunto: Mapped[str] = mapped_column(String(300), default="")
    html: Mapped[str] = mapped_column(Text, default="")
    atualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)


class ChecklistRh(Base):
    """Lista de documentos exigidos; vale para os tipos de cargo ligados a ela."""
    __tablename__ = "rh_checklists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Vale também para cargos sem classificação (tipo OUTRO)
    aplica_a_outros: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    itens: Mapped[list["ItemChecklistRh"]] = relationship(cascade="all, delete-orphan", order_by="ItemChecklistRh.ordem", lazy="selectin")
    classificacoes: Mapped[list["ChecklistClassificacao"]] = relationship(cascade="all, delete-orphan", order_by="ChecklistClassificacao.grupo, ChecklistClassificacao.nivel", lazy="selectin")


class ItemChecklistRh(Base):
    __tablename__ = "rh_checklist_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("rh_checklists.id", ondelete="CASCADE"), index=True)
    descricao: Mapped[str] = mapped_column(String(300))
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)


class ChecklistClassificacao(Base):
    """Ligação checklist ↔ classificação do cargo (grupo + nível, ex.: 1.15)."""
    __tablename__ = "rh_checklist_classificacoes"

    checklist_id: Mapped[int] = mapped_column(ForeignKey("rh_checklists.id", ondelete="CASCADE"), primary_key=True)
    grupo: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nivel: Mapped[int] = mapped_column(SmallInteger, primary_key=True)


class Admissao(Base):
    """Trilha de admissão de uma ficha de pré-cadastro."""
    __tablename__ = "rh_admissoes"
    __table_args__ = (UniqueConstraint("pre_cadastro_id", name="ux_rh_admissao_ficha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pre_cadastro_id: Mapped[int] = mapped_column(ForeignKey("rh_pre_cadastros.id", ondelete="CASCADE"), index=True)
    cargo_id: Mapped[int] = mapped_column(ForeignKey("rh_cargos.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="andamento", index=True)  # andamento | concluida | cancelada

    # Formulário de nomeação do GLPI ("CGP - Nomeações"): o próprio formulário abre os chamados de rede, e-mail, SEI, Compras SP, equipamento, estação, crachá, telefone e mobiliário
    solicitacoes: Mapped[dict | None] = mapped_column(JSON)
    chamado_glpi_id: Mapped[int | None] = mapped_column(Integer)
    chamado_url: Mapped[str | None] = mapped_column(String(500))
    # Foto da pessoa (opcional): vai no formulário do GLPI e, quando a conta existe, vira a foto do Diretório (intranet)
    foto_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="SET NULL"))
    # Itens criados pelo formulário de nomeação do GLPI (um por destino): [{"url", "texto"}]
    chamado_links: Mapped[list | None] = mapped_column(JSON)
    chamado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Documentos
    documentos_concluidos_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Resolução (texto da máscara, editável antes de publicar) e número reservado no Protocolo
    resolucao_html: Mapped[str | None] = mapped_column(Text)
    resolucao_gerada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    numero_protocolo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("protocolo_numeros.id", ondelete="SET NULL"))
    protocolo_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Resolução sem número (Parâmetros do RH sem tipo do Protocolo na hora de iniciar): a etapa do Protocolo não existe e o PDF do D.O.E. fica na própria admissão
    sem_numero: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    publicacao_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="SET NULL"))
    publicacao_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[publicacao_anexo_id])
    # Publicação no D.O.E. (o PDF fica anexado ao número do Protocolo, ou à admissão quando a resolução é sem número)
    publicado_em: Mapped[date | None] = mapped_column(Date)
    publicacao_registrada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # E-mail "Sua nomeação foi publicada"
    email_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Motivo da falha do envio automático (vazio = enviado ou ainda não tentado); o RH pode reenviar
    email_erro: Mapped[str | None] = mapped_column(String(500))
    # Posse e entrada no SGI
    posse_em: Mapped[date | None] = mapped_column(Date)
    termo_html: Mapped[str | None] = mapped_column(Text)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    documentos: Mapped[list["AdmissaoDocumento"]] = relationship(cascade="all, delete-orphan", order_by="AdmissaoDocumento.ordem", lazy="selectin")


class AdmissaoDocumento(Base):
    """Um documento do checklist, com o registro do envio ao Portal de Indicações."""
    __tablename__ = "rh_admissao_documentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admissao_id: Mapped[int] = mapped_column(ForeignKey("rh_admissoes.id", ondelete="CASCADE"), index=True)
    descricao: Mapped[str] = mapped_column(String(300))
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    enviado_em: Mapped[date | None] = mapped_column(Date)
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    enviado_por_nome: Mapped[str] = mapped_column(String(200), default="")
    registrado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comprovante_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="SET NULL"))
    observacao: Mapped[str] = mapped_column(String(500), default="")
    # Documento incluído durante a admissão (não veio do checklist do cargo): nunca obrigatório, pode ser excluído
    # enquanto a etapa estiver aberta. Tem descrição e o próprio arquivo, separado do comprovante de envio ao Portal.
    incluido_no_processo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    detalhe: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    arquivo_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="SET NULL"))
    incluido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    incluido_por_nome: Mapped[str] = mapped_column(String(200), default="", server_default="")
    incluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
