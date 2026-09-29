# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas da mensageria (mensagens e suas entregas a cada destinatário).
"""Mensageria interna: a caixa de mensagens de cada usuário.

- `Mensagem`: o conteúdo publicado (avulso, escrito por um usuário, ou automático, gerado pelo sistema).
- `EntregaMensagem`: a cópia de uma mensagem para um destinatário, com o estado dela (visualizada, ciente,
  encerrada) e o resultado do e-mail. A entrega guarda uma fotografia do assunto e do texto: editar a
  mensagem depois não muda o que o destinatário recebeu.

Nenhuma mensagem bloqueia a navegação. Avisos de pendência são encerrados automaticamente
(`encerrada_em`) quando a ação correspondente é feita no sistema.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc

PRIORIDADES = ("baixa", "normal", "alta", "critica")
CATEGORIAS = ("comunicado", "prazo", "pendencia", "revisao", "atribuicao", "indisponibilidade", "normativo")
ORIGENS = ("avulsa", "automatica")


def _lista_sql(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class Mensagem(Base):
    """Conteúdo publicado para um ou mais destinatários."""
    __tablename__ = "mensagens"
    __table_args__ = (
        CheckConstraint(f"prioridade IN ({_lista_sql(PRIORIDADES)})", name="ck_mensagens_prioridade"),
        CheckConstraint(f"categoria IN ({_lista_sql(CATEGORIAS)})", name="ck_mensagens_categoria"),
        CheckConstraint(f"origem IN ({_lista_sql(ORIGENS)})", name="ck_mensagens_origem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assunto: Mapped[str] = mapped_column(String(300))
    corpo: Mapped[str] = mapped_column(Text)
    prioridade: Mapped[str] = mapped_column(String(10), default="normal")
    categoria: Mapped[str] = mapped_column(String(20), default="comunicado")
    # Autor: nulo nas mensagens do sistema ("Sistema")
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    autor_nome: Mapped[str] = mapped_column(String(200), default="Sistema")
    publicada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    # Depois desta data a mensagem some da caixa (nulo = não expira)
    expira_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Caminho interno relacionado (ex.: /contratos/<id>)
    link: Mapped[str | None] = mapped_column(String(500))
    origem: Mapped[str] = mapped_column(String(12), default="avulsa")
    # Chave dos avisos automáticos: o mesmo evento não gera dois avisos para o mesmo destinatário
    chave: Mapped[str | None] = mapped_column(String(200), index=True)
    # Contrato a que o aviso se refere: excluir o contrato apaga os avisos dele
    contrato_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    # Abre uma janela (modal) na próxima vez que o destinatário usar o sistema
    abrir_em_janela: Mapped[bool] = mapped_column(Boolean, default=False)
    enviar_email: Mapped[bool] = mapped_column(Boolean, default=False)

    entregas: Mapped[list["EntregaMensagem"]] = relationship(back_populates="mensagem", cascade="all, delete-orphan")


class EntregaMensagem(Base):
    """A mensagem entregue a um destinatário, com o estado individual dela."""
    __tablename__ = "mensagens_entregas"
    __table_args__ = (
        UniqueConstraint("mensagem_id", "destinatario_id", name="uq_mensagens_entregas_mensagem_destinatario"),
        Index("ix_mensagens_entregas_destinatario_ciente", "destinatario_id", "ciente_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mensagem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mensagens.id", ondelete="CASCADE"), index=True)
    destinatario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    # Fotografia do que foi entregue
    assunto_copia: Mapped[str] = mapped_column(String(300))
    corpo_copia: Mapped[str] = mapped_column(Text)
    entregue_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    visualizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ciente_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Pendência resolvida pela própria ação no sistema (não exige mais ciência)
    encerrada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Resultado do e-mail (quando a mensagem também sai por e-mail)
    email_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_ok: Mapped[bool | None] = mapped_column(Boolean)
    email_erro: Mapped[str | None] = mapped_column(Text)

    mensagem: Mapped[Mensagem] = relationship(back_populates="entregas")
