# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato das preferências de colunas das listagens.
"""Schemas das preferências de colunas (`/api/preferencias/colunas/{tela}`)."""

from pydantic import BaseModel, Field, field_validator


class PreferenciaColunasLeitura(BaseModel):
    """Colunas escolhidas pelo usuário para a tela."""

    tela: str
    colunas: list[str] | None = Field(None, description="Visão pessoal: ids das colunas, na ordem de exibição. Nulo = a pessoa nunca escolheu.")
    padrao_global: list[str] | None = Field(None, description="Visão global da tela (definida pelo administrador), usada por quem não tem visão pessoal. Nulo = vale o padrão da própria tela.")


class GravacaoColunas(BaseModel):
    """Corpo do `PUT`: a lista completa, na ordem de exibição (substitui a anterior)."""

    colunas: list[str] = Field(..., min_length=1, max_length=80, description="Ids das colunas (letras minúsculas, números e `_`), sem repetir.")

    @field_validator("colunas")
    @classmethod
    def _ids_validos(cls, valor: list[str]) -> list[str]:
        vistos: list[str] = []
        for item in valor:
            item = item.strip()
            if not item or len(item) > 60 or not all(c.islower() or c.isdigit() or c == "_" for c in item):
                raise ValueError("cada coluna é um id com letras minúsculas, números e _")
            if item not in vistos:
                vistos.append(item)
        return vistos
