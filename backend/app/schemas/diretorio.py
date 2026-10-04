# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os formatos (schemas) da API do Diretório: ramais, aniversariantes e mural de parabéns.
"""Schemas de `/api/diretorio`. O ano de nascimento nunca aparece em nenhum deles."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ContatoResumo(BaseModel):
    """Pessoa citada dentro de outro cartão (chefia ou equipe)."""
    id: int
    nome: str
    cargo: str = ""
    ramal: str = ""
    foto_url: str | None = Field(None, description="Caminho da foto (exige o token de acesso); nulo quando não há foto.")


class Contato(ContatoResumo):
    """Cartão de visita de um servidor no diretório de ramais."""
    setor: str = Field("", description="Departamento/setor do perfil.")
    email: str = ""
    celular: str = ""
    whatsapp_url: str = Field("", description="Link `wa.me` montado a partir do celular, ou vazio.")
    linkedin: str = Field("", description="Link do perfil no LinkedIn, ou vazio.")
    andar: str = ""
    predio: str = ""
    local: str = Field("", description="Localização formatada (ex.: `4º andar - Bloco A`).")
    favorito: bool = Field(False, description="Se o usuário logado fixou este contato.")
    ferias_inicio: date | None = Field(None, description="Início das férias aprovadas, preenchido só enquanto a pessoa está de férias.")
    ferias_fim: date | None = Field(None, description="Último dia das férias; o selo some no dia seguinte.")


class ContatoDetalhe(Contato):
    """Cartão completo: acrescenta a chefia imediata e a equipe."""
    chefia: ContatoResumo | None = None
    equipe: list[ContatoResumo] = []


class PaginaContatos(BaseModel):
    """Página da lista de ramais."""
    itens: list[Contato]
    total: int
    pagina: int
    tamanho: int


class OpcoesFiltro(BaseModel):
    """Valores existentes para montar os filtros da tela de ramais."""
    setores: list[str]
    andares: list[str]
    predios: list[str]


class Aniversariante(BaseModel):
    """Pessoa que faz aniversário no período consultado."""
    id: int
    nome: str
    cargo: str = ""
    setor: str = ""
    ramal: str = ""
    email: str = ""
    foto_url: str | None = None
    dia: int
    mes: int
    e_hoje: bool
    dias_restantes: int = Field(..., description="Dias até o aniversário (0 = hoje). Negativo = já passou neste mês.")
    total_parabens: int = Field(0, description="Recados no mural deste aniversário.")
    ja_parabenizei: bool = Field(False, description="Se o usuário logado já deixou recado.")
    pode_parabenizar: bool = Field(False, description="Se o mural está aberto para o usuário logado (só no dia do aniversário e nunca no próprio mural).")


class Parabens(BaseModel):
    """Recado do mural de parabéns."""
    id: UUID
    autor_id: int
    autor_nome: str
    texto: str
    criado_em: datetime
    meu: bool = Field(False, description="Se foi escrito pelo usuário logado.")


class GravacaoParabens(BaseModel):
    """Corpo do recado."""
    texto: str = Field(..., min_length=1, max_length=500, description="Texto do recado (até 500 caracteres).")


class Preferencias(BaseModel):
    """Preferências do usuário logado no diretório."""
    foto_url: str | None = None
    foto_origem: str | None = Field(None, description="`upload` ou `ldap`.")
    ocultar_aniversario: bool = False


class AlteracaoPreferencias(BaseModel):
    """Corpo de `PATCH /diretorio/preferencias`."""
    ocultar_aniversario: bool
