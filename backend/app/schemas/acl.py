from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.usuarios import OpcaoUsuario

Nivel = Literal["LEITURA", "MODIFICACAO", "CONTROLE_TOTAL"]


class GravacaoRecurso(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=60, description="Identificador técnico usado no código. Normalizado para minúsculas, `a-z0-9_-`.")
    descricao: str = Field("", max_length=2000)
    url_base: str = Field("", max_length=255, description="Rota base do módulo no portal. Ex.: `/contratos`.")
    ativo: bool = Field(True, description="Recurso inativo não restringe acesso (política aberta).")

    @field_validator("nome", "descricao", "url_base")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        return valor.strip()


class LeituraRecurso(BaseModel):
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
    id: int
    nome: str
    sistemico: bool = False


class GravacaoRegra(BaseModel):
    recurso_id: int
    nivel: Nivel
    usuarios_ids: list[int] = Field(default_factory=list)
    setores_ids: list[int] = Field(default_factory=list)


class LeituraRegra(BaseModel):
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
    recurso_id: int
    nome: str
    slug: str
    url_base: str
    nivel: Nivel | None = Field(..., description="Nível efetivo; nulo = sem acesso.")
