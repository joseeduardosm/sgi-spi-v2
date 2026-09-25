from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.usuarios import OpcaoUsuario


class GravacaoSetor(BaseModel):
    nome: str = Field(..., min_length=1, max_length=150)
    setor_pai_id: int | None = Field(None, description="Setor pai (hierarquia). Nulo para raiz.")
    lider_id: int | None = Field(None, description="Usuário líder do setor.")
    sistemico: bool = Field(False, description="Grupo sistêmico (não institucional), ex.: Auditores.")
    ativo: bool = True
    membros_ids: list[int] = Field(default_factory=list, description="Usuários membros. Substitui a lista atual.")

    @field_validator("nome")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("não pode ser vazio")
        return valor


class LeituraSetor(BaseModel):
    id: int
    nome: str
    setor_pai_id: int | None
    setor_pai_nome: str | None
    lider_id: int | None
    lider_nome: str | None
    sistemico: bool
    ativo: bool
    total_membros: int
    total_subordinados: int
    criado_em: datetime
    atualizado_em: datetime


class DetalheSetor(LeituraSetor):
    membros: list[OpcaoUsuario]
