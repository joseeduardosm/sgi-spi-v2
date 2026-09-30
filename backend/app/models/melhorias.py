# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do Módulo Melhorias (sugestões dos usuários, prints anexados e histórico da triagem).
"""Módulo Melhorias: sugestões enviadas pelos usuários pelo botão flutuante "Sugerir melhoria".

- `SugestaoMelhoria`: a sugestão, com a tela de origem, a situação da triagem, a resposta ao autor (visível a ele)
  e a observação interna (só a triagem vê). Nome e login do autor ficam como retrato do momento do envio.
- `AnexoSugestao`: prints anexados (imagens guardadas pelo `servico_anexos`).
- `EventoSugestao`: histórico da triagem (mudanças de situação, resposta e conversão em tarefa).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.anexo import Anexo

SITUACOES_SUGESTAO = ("nova", "em_analise", "aceita", "recusada", "concluida")


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class SugestaoMelhoria(Base):
    """Sugestão de melhoria enviada por um usuário."""

    __tablename__ = "melhorias_sugestoes"
    __table_args__ = (CheckConstraint(f"situacao IN ({_lista(SITUACOES_SUGESTAO)})", name="ck_melhorias_sugestoes_situacao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Número público (#12), atribuído pelo serviço (maior + 1)
    numero: Mapped[int] = mapped_column(Integer, unique=True)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    autor_nome: Mapped[str] = mapped_column(String(250))
    autor_login: Mapped[str] = mapped_column(String(150))
    texto: Mapped[str] = mapped_column(Text)
    # Rota em que o usuário estava ao enviar e o módulo derivado dela (contratos, rh, tarefas…)
    tela: Mapped[str] = mapped_column(String(1000), default="")
    modulo: Mapped[str] = mapped_column(String(40), default="geral", index=True)
    situacao: Mapped[str] = mapped_column(String(20), default="nova", index=True)
    # Resposta que o autor vê em "Minhas sugestões"; a observação interna nunca vai ao autor
    resposta_publica: Mapped[str] = mapped_column(Text, default="")
    observacao_interna: Mapped[str] = mapped_column(Text, default="")
    tarefa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, index=True)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    atualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    atualizado_por_nome: Mapped[str] = mapped_column(String(250), default="")

    anexos: Mapped[list["AnexoSugestao"]] = relationship(back_populates="sugestao", cascade="all, delete-orphan", order_by="AnexoSugestao.ordem")
    eventos: Mapped[list["EventoSugestao"]] = relationship(back_populates="sugestao", cascade="all, delete-orphan", order_by="EventoSugestao.criado_em")


class AnexoSugestao(Base):
    """Print anexado à sugestão."""

    __tablename__ = "melhorias_anexos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sugestao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("melhorias_sugestoes.id", ondelete="CASCADE"), index=True)
    anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    sugestao: Mapped[SugestaoMelhoria] = relationship(back_populates="anexos")
    anexo: Mapped[Anexo] = relationship(lazy="joined")


class EventoSugestao(Base):
    """Passo da triagem: situação anterior e nova, resposta enviada ou tarefa criada."""

    __tablename__ = "melhorias_eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sugestao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("melhorias_sugestoes.id", ondelete="CASCADE"), index=True)
    descricao: Mapped[str] = mapped_column(String(500))
    situacao_anterior: Mapped[str] = mapped_column(String(20), default="")
    situacao_nova: Mapped[str] = mapped_column(String(20), default="")
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(250))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    sugestao: Mapped[SugestaoMelhoria] = relationship(back_populates="eventos")
