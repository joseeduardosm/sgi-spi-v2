# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos favoritos do menu (telas fixadas pelo usuário).
"""Schemas dos favoritos do menu (`/api/favoritos`)."""

from pydantic import BaseModel, Field, field_validator


class Favorito(BaseModel):
    """Uma tela favorita."""

    rota: str = Field(..., min_length=1, max_length=300, description="Rota do Angular, começando por `/` (ex.: `/contratos`, `/ramais?q=Maria`).")
    rotulo: str = Field(..., min_length=1, max_length=120, description="Texto mostrado no menu.")

    @field_validator("rota")
    @classmethod
    def _rota_interna(cls, valor: str) -> str:
        """Só rotas internas: começa com uma barra (e não com `//`, que seria outro endereço)."""
        valor = valor.strip()
        if not valor.startswith("/") or valor.startswith("//") or "://" in valor:
            raise ValueError("a rota deve ser interna, começando por \"/\"")
        return valor

    @field_validator("rotulo")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("informe o rótulo")
        return valor


class GravacaoFavoritos(BaseModel):
    """Corpo do `PUT /api/favoritos`: a lista completa, na ordem de exibição (substitui a anterior)."""

    itens: list[Favorito] = Field(default_factory=list, max_length=20, description="No máximo 20 favoritos.")


class RespostaFavoritos(BaseModel):
    """Favoritos do usuário, na ordem de exibição."""

    itens: list[Favorito]
