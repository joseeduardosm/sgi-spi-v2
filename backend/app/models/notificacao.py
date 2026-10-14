# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas das notificações (a notificação e a entrega dela a cada destinatário).
"""Notificações internas: a caixa de notificações de cada usuário.

- `Notificacao`: o conteúdo publicado (avulso, escrito por um usuário, ou automático, gerado pelo sistema).
- `EntregaNotificacao`: a cópia de uma notificação para um destinatário, com o estado dela (visualizada, ciente,
  encerrada) e o resultado do e-mail. A entrega guarda uma fotografia do assunto e do texto: editar a
  notificação depois não muda o que o destinatário recebeu.

Nenhuma notificação bloqueia a navegação. Avisos de pendência são encerrados automaticamente
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


class Notificacao(Base):
    """Conteúdo publicado para um ou mais destinatários."""
    __tablename__ = "notificacoes"
    __table_args__ = (
        CheckConstraint(f"prioridade IN ({_lista_sql(PRIORIDADES)})", name="ck_notificacoes_prioridade"),
        CheckConstraint(f"categoria IN ({_lista_sql(CATEGORIAS)})", name="ck_notificacoes_categoria"),
        CheckConstraint(f"origem IN ({_lista_sql(ORIGENS)})", name="ck_notificacoes_origem"),
    )

    # O id é gerado no Python (não no banco): o despacho depois do commit precisa dele antes de consultar qualquer coisa
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assunto: Mapped[str] = mapped_column(String(300))
    corpo: Mapped[str] = mapped_column(Text)
    prioridade: Mapped[str] = mapped_column(String(10), default="normal")
    categoria: Mapped[str] = mapped_column(String(20), default="comunicado")
    # Autor: nulo nas notificações do sistema ("Sistema")
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    autor_nome: Mapped[str] = mapped_column(String(200), default="Sistema")
    publicada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    # Depois desta data a notificação some da caixa (nulo = não expira)
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
    # Evento do catálogo (`app.services.notificacoes.catalogo`) que originou a notificação; nulo nas anteriores ao catálogo e nas avulsas antigas
    evento: Mapped[str | None] = mapped_column(String(60), index=True)
    # Tarefa a que o aviso se refere (permite "silenciar esta tarefa"); excluir a tarefa apaga os avisos dela
    tarefa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), index=True)

    entregas: Mapped[list["EntregaNotificacao"]] = relationship(back_populates="notificacao", cascade="all, delete-orphan")


class EntregaNotificacao(Base):
    """A notificação entregue a um destinatário, com o estado individual dela."""
    __tablename__ = "notificacoes_entregas"
    __table_args__ = (
        UniqueConstraint("notificacao_id", "destinatario_id", name="uq_notificacoes_entregas_notificacao_destinatario"),
        Index("ix_notificacoes_entregas_destinatario_ciente", "destinatario_id", "ciente_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    notificacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notificacoes.id", ondelete="CASCADE"), index=True)
    destinatario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    # Fotografia do que foi entregue
    assunto_copia: Mapped[str] = mapped_column(String(300))
    corpo_copia: Mapped[str] = mapped_column(Text)
    entregue_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    visualizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ciente_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Pendência resolvida pela própria ação no sistema (não exige mais ciência)
    encerrada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Canais externos, uma fotografia da preferência do destinatário no momento da entrega (a caixa recebe sempre)
    canal_email: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    canal_navegador: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    canal_desktop: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # E-mail em resumo (diário ou semanal): a entrega espera o resumo em vez de sair na hora
    email_resumo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Resultado do e-mail. `email_enviado_em` é também a reivindicação do envio (só quem a preenche primeiro envia)
    email_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_ok: Mapped[bool | None] = mapped_column(Boolean)
    email_erro: Mapped[str | None] = mapped_column(Text)
    # Resultado do envio ao navegador (Web Push); `navegador_enviado_em` também reivindica o envio
    navegador_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    navegador_ok: Mapped[bool | None] = mapped_column(Boolean)
    navegador_erro: Mapped[str | None] = mapped_column(Text)

    notificacao: Mapped[Notificacao] = relationship(back_populates="entregas")
