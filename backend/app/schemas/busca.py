# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato da resposta da busca global do portal.
"""Schemas da busca global (`GET /api/busca`)."""

from typing import Literal

from pydantic import BaseModel, Field


class ResultadoBusca(BaseModel):
    """Um resultado da busca global, pronto para a tela montar o link."""

    tipo: Literal["contrato", "empresa", "setor", "pessoa", "tarefa", "contratacao"] = Field(..., description="Tipo do resultado (agrupa a lista na tela).")
    id: str = Field(..., description="Identificador do registro (texto).")
    titulo: str
    subtitulo: str = ""
    rota: str = Field(..., description="Rota do Angular que abre o registro (pode trazer `?q=`).")


class RespostaBusca(BaseModel):
    """Resultados da busca global, já filtrados pelas permissões do usuário."""

    itens: list[ResultadoBusca]
