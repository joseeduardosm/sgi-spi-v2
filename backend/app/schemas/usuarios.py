import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.servico_perfil import CAMPOS_OBRIGATORIOS

PADRAO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DadosPerfil(BaseModel):
    """Perfil institucional. Textos são aparados; vazios são permitidos (exceto na revalidação)."""

    nome_completo: str = Field("", max_length=200, description="Nome completo.")
    email: str = Field("", max_length=254, description="E-mail institucional.")
    ramal: str = Field("", max_length=20, description="Ramal.")
    celular: str = Field("", max_length=30, description="Celular.")
    cargo: str = Field("", max_length=150, description="Cargo.")
    departamento: str = Field("", max_length=150, description="Departamento.")
    andar: str = Field("", max_length=30, description="Andar.")
    predio: str = Field("", max_length=100, description="Prédio.")
    data_nascimento: date | None = Field(None, description="Data de nascimento (AAAA-MM-DD).")
    gestor_id: int | None = Field(None, description="ID do gestor imediato.")

    @field_validator("nome_completo", "email", "ramal", "celular", "cargo", "departamento", "andar", "predio")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        return valor.strip()

    @field_validator("email")
    @classmethod
    def _validar_email(cls, valor: str) -> str:
        if valor and not PADRAO_EMAIL.match(valor):
            raise ValueError("e-mail inválido")
        return valor


class RevisaoPerfil(DadosPerfil):
    """Revalidação do próprio perfil: todos os campos obrigatórios devem estar preenchidos."""

    @model_validator(mode="after")
    def _exigir_obrigatorios(self) -> "RevisaoPerfil":
        pendentes = [rotulo for campo, rotulo in CAMPOS_OBRIGATORIOS.items() if not getattr(self, campo)]
        if pendentes:
            raise ValueError("Preencha os campos obrigatórios: " + ", ".join(pendentes) + ".")
        return self


class PerfilLeitura(DadosPerfil):
    model_config = ConfigDict(from_attributes=True)

    gestor_nome: str | None = Field(None, description="Nome do gestor imediato.")
    perfil_revisado_em: datetime | None = Field(None, description="Última revalidação do perfil.")


class CriacaoUsuario(BaseModel):
    login: str = Field(..., min_length=1, max_length=150, pattern=r"^[A-Za-z0-9._@-]+$", description="Login (letras, números, `.`, `_`, `-`, `@`).")
    senha: str = Field(..., min_length=8, max_length=128, description="Senha local, mínimo 8 caracteres.")
    ativo: bool = True
    superusuario: bool = Field(False, description="Administrador do sistema (papel SuperRoot).")
    perfil: DadosPerfil = DadosPerfil()


class AlteracaoUsuario(BaseModel):
    senha: str | None = Field(None, max_length=128, description="Nova senha local (mín. 8). Vazia ou ausente mantém a atual.")
    ativo: bool
    superusuario: bool
    perfil: DadosPerfil

    @field_validator("senha")
    @classmethod
    def _validar_senha(cls, valor: str | None) -> str | None:
        if valor and len(valor) < 8:
            raise ValueError("a nova senha deve ter ao menos 8 caracteres")
        return valor or None


class DetalheUsuario(BaseModel):
    id: int
    login: str
    ativo: bool
    superusuario: bool
    origem: str = Field(..., description="`local`, `ldap` ou `local_ldap`.")
    possui_senha_local: bool = Field(..., description="A conta possui senha local utilizável.")
    diretorio_nome: str | None = Field(None, description="Diretório LDAP vinculado.")
    id_externo: str | None = Field(None, description="Identificador no diretório (objectGUID).")
    perfil: PerfilLeitura
    perfil_completo: bool = Field(..., description="Todos os campos obrigatórios preenchidos.")
    revisao_obrigatoria: bool = Field(..., description="Revalidação vencida (mais de 30 dias) ou nunca feita.")
    setores: list[str] = Field(default_factory=list, description="Setores dos quais o usuário é membro.")
    ultimo_acesso_em: datetime | None = None
    criado_em: datetime
    atualizado_em: datetime


class PaginaUsuarios(BaseModel):
    itens: list[DetalheUsuario]
    total: int = Field(..., description="Total de registros que atendem ao filtro.")
    pagina: int
    tamanho_pagina: int


class OpcaoUsuario(BaseModel):
    """Forma reduzida para seletores (gestor, membros, regras de ACL)."""

    id: int
    login: str
    nome_completo: str
    cargo: str = ""
    ativo: bool = True
