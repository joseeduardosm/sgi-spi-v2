# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de entrada e saída das rotas de ACL.
"""Formatos de entrada e saída das rotas de ACL (recursos, regras e acessos efetivos)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.usuarios import OpcaoUsuario

# Níveis aceitos; o Literal faz o Pydantic recusar qualquer outro valor com erro 422
Nivel = Literal["LEITURA", "MODIFICACAO", "CONTROLE_TOTAL"]


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


class LeituraRecurso(BaseModel):
    """Recurso como aparece na listagem da administração."""
    id: int
    nome: str
    slug: str
    descricao: str
    url_base: str
    ativo: bool
    total_regras: int = Field(..., description="Quantidade de regras. Zero = recurso aberto.")
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
