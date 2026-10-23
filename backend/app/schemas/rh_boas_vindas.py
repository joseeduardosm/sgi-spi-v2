# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os formatos das rotas de boas-vindas do primeiro acesso e da bio.
"""Schemas de boas-vindas e bio."""

from pydantic import BaseModel, Field


class BoasVindas(BaseModel):
    pendente: bool = Field(description="`true` no primeiro acesso: a tela mostra o aviso e depois leva ao cadastro.")
    titulo: str = ""
    html: str = Field("", description="Texto do modelo \"Boas-vindas\" já preenchido (HTML seguro: os valores são escapados).")
    nome: str = ""


class BioLeitura(BaseModel):
    bio_texto: str
    bio_visivel: bool


class BioGravacao(BaseModel):
    bio_texto: str = Field("", max_length=3000, description="Idade, formação, experiências... texto livre.")
    bio_visivel: bool = Field(False, description="Libera a bio na busca de usuários e no cartão de contato. Sem texto, fica oculta.")
