# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de entrada e saída de setores.
"""Formatos de entrada e saída das rotas de setores."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.usuarios import OpcaoUsuario


class OpcaoDepartamento(BaseModel):
    """Setor oferecido no combobox "Departamento" do perfil do usuário."""
    id: int
    nome: str = Field(..., description="Nome do setor, gravado como departamento do usuário.")
    nivel: int = Field(..., description="Profundidade na hierarquia (0 = raiz), para recuar a opção na lista.")


class GravacaoSetor(BaseModel):
    """Dados enviados para criar ou alterar um setor."""
    nome: str = Field(..., min_length=1, max_length=150)
    setor_pai_id: int | None = Field(None, description="Setor pai (hierarquia). Nulo para raiz.")
    lider_id: int | None = Field(None, description="Usuário líder do setor.")
    sistemico: bool = Field(False, description="Grupo sistêmico (não institucional), ex.: Auditores.")
    ativo: bool = True
    membros_ids: list[int] = Field(default_factory=list, description="Usuários membros. Substitui a lista atual.")

    @field_validator("nome")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        """Tira espaços das pontas e recusa nome em branco."""
        valor = valor.strip()
        if not valor:
            raise ValueError("não pode ser vazio")
        return valor


class LeituraSetor(BaseModel):
    """Setor na listagem, com nomes já resolvidos (pai e líder) e contagens para a tabela."""
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
    """Setor com a lista completa de membros (tela de detalhe/edição)."""
    membros: list[OpcaoUsuario]
