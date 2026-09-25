# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas de setores e de seus membros.
"""Setores: unidades institucionais e grupos sistêmicos. Funcionam como grupos de acesso na ACL."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class Setor(Base):
    """Setor institucional ou grupo sistêmico, com hierarquia opcional (setor pai) e líder."""
    __tablename__ = "setores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    # Hierarquia: RESTRICT impede excluir um setor que ainda tenha subordinados
    setor_pai_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="RESTRICT"), index=True)
    # Líder do setor; se o usuário for excluído, o setor fica sem líder (SET NULL)
    lider_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Sistêmico: grupo de acesso sem correspondência na estrutura institucional (ex.: "Auditores")
    sistemico: Mapped[bool] = mapped_column(Boolean, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)


# Nome único sem diferenciar maiúsculas/minúsculas ("TI" e "ti" seriam o mesmo setor)
Index("ux_setores_nome_minusculo", func.lower(Setor.nome), unique=True)


class MembroSetor(Base):
    """Associação usuário ↔ setor (tabela de ligação muitos-para-muitos)."""
    __tablename__ = "membros_setor"

    # Chave primária composta: o mesmo usuário não entra duas vezes no mesmo setor
    setor_id: Mapped[int] = mapped_column(ForeignKey("setores.id", ondelete="CASCADE"), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
