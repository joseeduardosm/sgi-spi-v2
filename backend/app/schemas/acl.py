# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de entrada e saída das rotas de ACL.
"""Formatos de entrada e saída das rotas de ACL (recursos, regras e acessos efetivos)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.usuarios import OpcaoUsuario

# Níveis aceitos; o Literal faz o Pydantic recusar qualquer outro valor com erro 422
Nivel = Literal["LEITURA", "MODIFICACAO", "CONTROLE_TOTAL"]


class TextoNivel(BaseModel):
    """Como um nível aparece em um recurso: nome curto e o que ele libera ali."""
    rotulo: str = Field(..., description="Nome curto do nível neste módulo. Ex.: `Reservar números de documentos`.")
    descricao: str = Field(..., description="Frase do que o nível libera neste módulo.")


NiveisTextos = dict[Nivel, TextoNivel]
DESCRICAO_NIVEIS = "Textos dos três níveis neste recurso (definidos em `services/acl_niveis.py`): o que cada um libera naquele módulo."


class GravacaoRecurso(BaseModel):
    """Dados para cadastrar ou alterar um recurso (módulo) protegido."""
    nome: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=60, description="Identificador técnico usado no código. Normalizado para minúsculas, `a-z0-9_-`.")
    descricao: str = Field("", max_length=2000)
    url_base: str = Field("", max_length=255, description="Rota base do módulo no portal. Ex.: `/contratos`.")
    ativo: bool = Field(True, description="Recurso inativo não restringe acesso (política aberta).")

    @field_validator("nome", "descricao", "url_base")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        """Remove espaços das pontas dos textos."""
        return valor.strip()


class AcaoModulo(BaseModel):
    """Uma ação (permissão independente) que o módulo oferece nos perfis."""
    codigo: str = Field(..., description="Código da ação: `LEITURA`, `MODIFICACAO` ou `CONTROLE_TOTAL` (a porta que ela abre nas rotas do módulo) ou o de uma ação própria do módulo (ex.: `LANCAR_OB`, em Contratos).")
    rotulo: str = Field(..., description="Nome da ação neste módulo (ex.: `Cadastrar bens e solicitar`).")
    descricao: str = Field(..., description="O que a ação libera.")


class LeituraRecurso(BaseModel):
    """Recurso como aparece na listagem da administração."""
    id: int
    nome: str
    slug: str
    descricao: str
    url_base: str
    ativo: bool
    total_regras: int = Field(..., description="Quantidade de regras (por usuário e setor). Sem regras **e** sem perfis (`total_perfis`) = recurso aberto.")
    acoes: list[AcaoModulo] = Field(default_factory=list, description="Ações que o módulo oferece nos perfis (permissões independentes).")
    total_perfis: int = Field(0, description="Quantidade de perfis ativos com direito neste recurso (também fecha o recurso a quem não está contemplado).")
    niveis: NiveisTextos = Field(..., description=DESCRICAO_NIVEIS)
    criado_em: datetime
    atualizado_em: datetime


class OpcaoSetor(BaseModel):
    """Setor em forma reduzida, para seletores e para exibir nas regras."""
    id: int
    nome: str
    sistemico: bool = False


class GravacaoRegra(BaseModel):
    """Dados de uma regra: o nível concedido e a quem (usuários e/ou setores)."""
    recurso_id: int
    nivel: Nivel
    usuarios_ids: list[int] = Field(default_factory=list)
    setores_ids: list[int] = Field(default_factory=list)


class LeituraRegra(BaseModel):
    """Regra com os nomes já resolvidos para exibição."""
    id: int
    recurso_id: int
    recurso_nome: str
    recurso_slug: str
    nivel: Nivel
    niveis: NiveisTextos = Field(..., description=DESCRICAO_NIVEIS)
    usuarios: list[OpcaoUsuario]
    setores: list[OpcaoSetor]
    criado_em: datetime
    atualizado_em: datetime


class AcessoEfetivo(BaseModel):
    """Nível efetivo do usuário em um recurso, somando as regras diretas e as dos seus setores."""
    recurso_id: int
    nome: str
    slug: str
    url_base: str
    nivel: Nivel | None = Field(..., description="Nível efetivo; nulo = sem acesso.")
    niveis: NiveisTextos = Field(..., description=DESCRICAO_NIVEIS)
    acoes: list[str] = Field(default_factory=list, description="Ações que o perfil ativo concede no módulo (independentes). O `nivel` mostrado é o maior entre o das regras e o da maior ação marcada, só para a interface decidir o que exibir; o backend confere a ação exata de cada rota.")
    origens: dict[str, Nivel] = Field(default_factory=dict, description="De onde vem o nível: `perfil` (perfil ativo), `setor` e `direta`, cada um com o seu nível; o efetivo é o maior. Vazio: recurso aberto ou SuperRoot.")


# --- Perfis de acesso ---------------------------------------------------------------------------

class GravacaoPerfil(BaseModel):
    """Dados para cadastrar ou alterar um perfil de acesso."""
    nome: str = Field(..., min_length=1, max_length=100, description="Nome do perfil (único, sem diferenciar maiúsculas).")
    descricao: str = Field("", max_length=2000)
    ativo: bool = Field(True, description="Perfil inativo não vale para ninguém (nem aparece no menu do usuário).")

    @field_validator("nome", "descricao")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        return valor.strip()


class LeituraPerfil(BaseModel):
    """Perfil na lista da administração."""
    id: int
    nome: str
    descricao: str
    ativo: bool
    total_usuarios: int
    total_setores: int = Field(0, description="Quantos setores e grupos sistêmicos recebem o perfil.")
    total_direitos: int = Field(..., description="Quantos módulos foram adicionados ao perfil.")
    criado_em: datetime
    atualizado_em: datetime


class DireitoPerfilModulo(BaseModel):
    """Módulo adicionado ao perfil, com as ações marcadas."""
    recurso_id: int
    recurso_nome: str
    recurso_slug: str
    acoes: list[str] = Field(..., description="Ações marcadas (independentes: nenhuma inclui as outras).")
    acoes_disponiveis: list[AcaoModulo] = Field(..., description="Todas as ações que o módulo oferece.")


class GravacaoAcoesModulo(BaseModel):
    """Ações que o perfil concede em um módulo (substitui as anteriores)."""
    acoes: list[str] = Field(..., min_length=1, max_length=10, description="Ao menos uma ação, entre as que o módulo oferece (`acoes` de `LeituraRecurso`).")


class UsuarioDoPerfil(BaseModel):
    """Usuário que tem o perfil."""
    id: int
    login: str
    nome_completo: str
    cargo: str | None = None
    ativo: bool
    padrao: bool = Field(..., description="Este é o perfil padrão do usuário (o que vale ao entrar).")


class SetorDoPerfil(BaseModel):
    """Setor ou grupo sistêmico que recebe o perfil (os membros passam a tê-lo)."""
    id: int
    nome: str
    sistemico: bool
    setor_pai_id: int | None = None


class DetalhePerfil(LeituraPerfil):
    """Perfil com a matriz de direitos, os usuários e os setores."""
    direitos: list[DireitoPerfilModulo]
    usuarios: list[UsuarioDoPerfil]
    setores: list[SetorDoPerfil] = Field(default_factory=list, description="Setores e grupos sistêmicos que recebem o perfil: quem é membro deles passa a ter o perfil.")


class GravacaoSetoresPerfil(BaseModel):
    """Substitui os setores e grupos que recebem o perfil (a tela marca os filhos junto com o pai; a API guarda exatamente os ids enviados)."""
    setores_ids: list[int] = Field(default_factory=list, max_length=2000)


class GravacaoUsuariosPerfil(BaseModel):
    """Substitui os usuários que têm o perfil (quem entra sem outro perfil passa a ter este como padrão)."""
    usuarios_ids: list[int] = Field(default_factory=list, max_length=2000)


class PerfilDoUsuario(BaseModel):
    """Perfil atribuído a um usuário."""
    perfil_id: int
    nome: str
    ativo: bool
    padrao: bool
    via_setores: list[str] = Field(default_factory=list, description="Setores ou grupos pelos quais o usuário recebe o perfil (vazio: atribuído diretamente).")
    direto: bool = Field(True, description="Perfil atribuído diretamente ao usuário (só estes se alteram em `PUT .../perfis`).")


class GravacaoPerfisDoUsuario(BaseModel):
    """Substitui os perfis de um usuário e define qual é o padrão."""
    perfis_ids: list[int] = Field(default_factory=list, max_length=100)
    padrao_id: int | None = Field(None, description="Perfil padrão (precisa estar em `perfis_ids`; sem ele, vale o primeiro).")
