"""
===============================================================================
ARQUIVO: usuario.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Definir a tabela de usuários do portal e os papéis especiais.

RESUMO TÉCNICO:
- Papel: constantes de papéis (hoje só SuperRoot, coluna superusuario).
- OrigemUsuario: como a conta autentica. Conta local tem senha própria
  (hash bcrypt); conta ldap confere a senha no Active Directory e recebe os
  dados da sincronização; local_ldap aceita as duas formas.
- Usuario: identificação, vínculo LDAP (diretório, objectGUID, DN), perfil
  institucional, foto, tema, bio e datas de acesso e boas-vindas.
- Índice único em lower(login): login sem diferenciar maiúsculas.

FINALIDADE DE NEGÓCIO:
Representar cada pessoa que usa o SGI e os dados do perfil institucional
(ramal, cargo, setor, aniversário), que o próprio usuário revalida a cada
30 dias para manter o diretório de pessoas atualizado.

CONTEXTO NO SISTEMA:
Tabela central: referenciada por quase todos os módulos (autoria,
responsáveis, ACL, RH, setores). Usada na autenticação (local e LDAP), na
sincronização com diretorios_ldap e nas dependências de autorização
(possui_papel). Os formatos de API ficam em schemas/autenticacao.py e afins.

===============================================================================
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, false, func
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
    """Tabela `usuarios`: identificação, vínculo com o LDAP e perfil institucional.

    Cada classe que herda de `Base` vira uma tabela. `Mapped[...]` declara o tipo da coluna em
    Python (com `| None` quando aceita nulo) e `mapped_column(...)` os detalhes no banco.
    LDAP é o protocolo usado para consultar o Active Directory (AD), o cadastro de contas de rede.
    """
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String(150))
    # Somente contas locais possuem hash utilizável; contas criadas pelo LDAP ficam com None
    hash_senha: Mapped[str | None] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    superusuario: Mapped[bool] = mapped_column(Boolean, default=False)
    # Conta de uma integração entre sistemas (ex.: lançar a OB): não tem pessoa para preencher e confirmar o cadastro todo mês, então é dispensada disso
    # (só disso: ela NÃO ganha os recursos exclusivos da conta root)
    conta_integracao: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    origem: Mapped[str] = mapped_column(String(20), default=OrigemUsuario.LOCAL)

    # Vínculo LDAP (preenchido pela sincronização com o AD; vazio nas contas só locais)
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
    # Tema da interface escolhido pelo usuário: claro, escuro ou auto (segue o sistema). Não passa pela validação da CGP
    tema: Mapped[str] = mapped_column(String(10), default="auto", server_default="auto")
    # Link do perfil no LinkedIn (opcional; sempre https://…linkedin.com/…). Não passa pela validação da CGP
    linkedin: Mapped[str] = mapped_column(String(200), default="", server_default="")
    cargo: Mapped[str] = mapped_column(String(150), default="")
    departamento: Mapped[str] = mapped_column(String(150), default="")
    andar: Mapped[str] = mapped_column(String(30), default="")
    predio: Mapped[str] = mapped_column(String(100), default="")
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    gestor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Foto do cartão de ramais (anexo em imagem). `foto_origem`: "upload" (enviada pelo usuário) ou "ldap" (thumbnailPhoto do AD)
    foto_anexo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("anexos.id", ondelete="SET NULL", use_alter=True, name="fk_usuarios_foto_anexo_id"))
    foto_origem: Mapped[str | None] = mapped_column(String(10))
    # Opt-out: quando verdadeiro, o usuário não aparece nas listas de aniversariantes nem recebe recados no mural
    ocultar_aniversario: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Data da última revalidação do perfil; vazia ou antiga demais = perfil pendente
    perfil_revisado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Boas-vindas do primeiro acesso: vazio = ainda não viu o aviso (a migração marcou quem já usava o sistema); o e-mail sai uma única vez
    boas_vindas_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    boas_vindas_email_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bio opcional (idade, formação, experiências...): só entra na busca e no cartão quando a pessoa libera (`bio_visivel`)
    bio_texto: Mapped[str] = mapped_column(Text, default="", server_default="")
    bio_visivel: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    ultimo_acesso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    # `@property` cria um atributo calculado, lido sem parênteses (usuario.papeis)
    @property
    def papeis(self) -> list[str]:
        """Lista de papéis do usuário, derivada da coluna `superusuario`."""
        return [Papel.SUPER_ROOT] if self.superusuario else []

    def possui_papel(self, papel: str) -> bool:
        """Indica se o usuário tem o papel informado (usado pelas dependências de autorização)."""
        return papel in self.papeis


# Login único sem diferenciar maiúsculas/minúsculas
Index("ux_usuarios_login_minusculo", func.lower(Usuario.login), unique=True)
