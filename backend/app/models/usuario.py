# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela de usuários do portal e seus papéis.
"""Usuário do portal: conta local, corporativa (LDAP) ou ambas.

- Conta **local**: tem senha própria guardada como hash bcrypt.
- Conta **ldap**: a senha é conferida no Active Directory; os dados vêm da sincronização.
- Conta **local_ldap**: aceita as duas formas de login.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class Papel:
    """Papéis especiais. Hoje só existe o SuperRoot (administrador), guardado na coluna `superusuario`."""
    SUPER_ROOT = "SuperRoot"


class OrigemUsuario:
    """Valores possíveis da coluna `origem` (como a conta foi criada e como autentica)."""
    LOCAL = "local"
    LDAP = "ldap"
    LOCAL_LDAP = "local_ldap"


class Usuario(Base):
    """Tabela `usuarios`: identificação, vínculo com o LDAP e perfil institucional."""
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String(150))
    # Somente contas locais possuem hash utilizável; contas criadas pelo LDAP ficam com None
    hash_senha: Mapped[str | None] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    superusuario: Mapped[bool] = mapped_column(Boolean, default=False)
    origem: Mapped[str] = mapped_column(String(20), default=OrigemUsuario.LOCAL)

    # Vínculo LDAP
    # Diretório de onde a conta veio; se o diretório for excluído, o usuário continua existindo
    diretorio_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("diretorios_ldap.id", ondelete="SET NULL"), index=True
    )
    # Identificador estável no AD (objectGUID) e o caminho completo da entrada (DN)
    id_externo: Mapped[str | None] = mapped_column(String(64), index=True)
    dn: Mapped[str | None] = mapped_column(String(500))

    # Perfil institucional
    # Estes dados precisam ser revalidados pelo próprio usuário a cada 30 dias
    nome_completo: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    ramal: Mapped[str] = mapped_column(String(20), default="")
    celular: Mapped[str] = mapped_column(String(30), default="")
    cargo: Mapped[str] = mapped_column(String(150), default="")
    departamento: Mapped[str] = mapped_column(String(150), default="")
    andar: Mapped[str] = mapped_column(String(30), default="")
    predio: Mapped[str] = mapped_column(String(100), default="")
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    gestor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Data da última revalidação do perfil; vazia ou antiga demais = perfil pendente
    perfil_revisado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ultimo_acesso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    @property
    def papeis(self) -> list[str]:
        """Lista de papéis do usuário, derivada da coluna `superusuario`."""
        return [Papel.SUPER_ROOT] if self.superusuario else []

    def possui_papel(self, papel: str) -> bool:
        """Indica se o usuário tem o papel informado (usado pelas dependências de autorização)."""
        return papel in self.papeis


# Login único sem diferenciar maiúsculas/minúsculas
Index("ux_usuarios_login_minusculo", func.lower(Usuario.login), unique=True)
