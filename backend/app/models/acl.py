# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas de recursos e regras do controle de acesso (ACL).
"""Controle de acesso por recurso (ACL).

Um **recurso** é um módulo do portal (ex.: `contratos`). Uma **regra** concede um nível de
acesso nesse recurso a usuários e/ou setores. Enquanto um recurso não tem regras, ele fica
aberto a todos os usuários autenticados; a partir da primeira regra, só acessa quem estiver
contemplado ("lista positiva"). O SuperRoot sempre tem controle total.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc


class NivelAcl:
    """Níveis de acesso, do menor para o maior. Um nível maior inclui os poderes dos menores."""
    LEITURA = "LEITURA"
    MODIFICACAO = "MODIFICACAO"
    CONTROLE_TOTAL = "CONTROLE_TOTAL"

    # Posição numérica de cada nível, para comparar "tem pelo menos X"
    ORDEM = {LEITURA: 1, MODIFICACAO: 2, CONTROLE_TOTAL: 3}
    TODOS = (LEITURA, MODIFICACAO, CONTROLE_TOTAL)

    @classmethod
    def posicao(cls, nivel: str | None) -> int:
        """Posição do nível na hierarquia (0 = sem acesso)."""
        return cls.ORDEM.get(nivel or "", 0)


class RecursoAcl(Base):
    """Módulo do portal protegido por ACL, identificado pelo slug usado no código."""

    __tablename__ = "acl_recursos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    descricao: Mapped[str] = mapped_column(Text, default="")
    url_base: Mapped[str] = mapped_column(String(255), default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)


# Nome do recurso único sem diferenciar maiúsculas/minúsculas
Index("ux_acl_recursos_nome_minusculo", func.lower(RecursoAcl.nome), unique=True)

# Tabelas de ligação: quais usuários e quais setores cada regra contempla
acl_regras_usuarios = Table(
    "acl_regras_usuarios",
    Base.metadata,
    Column("regra_id", ForeignKey("acl_regras.id", ondelete="CASCADE"), primary_key=True),
    Column("usuario_id", ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True, index=True),
)

acl_regras_setores = Table(
    "acl_regras_setores",
    Base.metadata,
    Column("regra_id", ForeignKey("acl_regras.id", ondelete="CASCADE"), primary_key=True),
    Column("setor_id", ForeignKey("setores.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class RegraAcl(Base):
    """Concede um nível de acesso a um recurso para usuários e/ou setores."""

    __tablename__ = "acl_regras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recurso_id: Mapped[int] = mapped_column(ForeignKey("acl_recursos.id", ondelete="CASCADE"), index=True)
    nivel: Mapped[str] = mapped_column(String(20))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    # `joined` e `selectin` carregam o recurso, os usuários e os setores junto com a regra,
    # evitando uma consulta extra por regra ao montar as listas
    recurso: Mapped[RecursoAcl] = relationship(lazy="joined")
    usuarios = relationship("Usuario", secondary=acl_regras_usuarios, lazy="selectin", order_by="Usuario.nome_completo")
    setores = relationship("Setor", secondary=acl_regras_setores, lazy="selectin", order_by="Setor.nome")
