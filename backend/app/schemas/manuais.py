# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato das respostas dos manuais (conteúdo do BookStack lido pelo portal).
"""Schemas dos manuais (`/api/manuais`): estantes, livros, páginas, busca e a configuração da integração."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ResumoLivro(BaseModel):
    """Livro de uma estante (ou sem estante)."""

    id: int
    nome: str
    descricao: str = ""


class Estante(BaseModel):
    """Estante com os livros dela."""

    id: int
    nome: str
    descricao: str = ""
    livros: list[ResumoLivro]


class ListaManuais(BaseModel):
    """Resposta do `GET /api/manuais`: estantes e os livros que não estão em nenhuma estante."""

    estantes: list[Estante]
    livros_avulsos: list[ResumoLivro]
    url_origem: str = Field(..., description="Endereço do BookStack (para o link \"abrir no BookStack\").")


class ItemSumario(BaseModel):
    """Entrada do sumário de um livro: página ou capítulo (com as páginas dele)."""

    tipo: Literal["pagina", "capitulo"]
    id: int
    nome: str
    paginas: list["ItemSumario"] = Field(default_factory=list, description="Só para capítulo.")


class DetalheLivro(BaseModel):
    """Resposta do `GET /api/manuais/livros/{id}`."""

    id: int
    nome: str
    descricao: str = ""
    sumario: list[ItemSumario]
    primeira_pagina_id: int | None = Field(None, description="Primeira página na ordem de leitura (para o botão \"começar\").")
    url_origem: str


class PaginaVizinha(BaseModel):
    """Página anterior ou próxima na ordem de leitura do livro."""

    id: int
    nome: str


class DetalhePagina(BaseModel):
    """Resposta do `GET /api/manuais/paginas/{id}`. O HTML já vem sanitizado."""

    id: int
    nome: str
    livro_id: int
    livro_nome: str
    capitulo_id: int | None = None
    capitulo_nome: str | None = None
    html: str
    atualizado_em: datetime | None = None
    anterior: PaginaVizinha | None = None
    proxima: PaginaVizinha | None = None
    url_origem: str = Field(..., description="Endereço da página no BookStack (onde ela é editada).")


class ResultadoBuscaManual(BaseModel):
    """Um resultado da busca nos manuais."""

    tipo: Literal["pagina", "capitulo", "livro"]
    id: int
    nome: str
    livro_id: int | None = None
    livro_nome: str | None = None
    trecho: str = Field("", description="Trecho com o termo destacado em `<strong>` (HTML seguro).")
    rota: str = Field(..., description="Rota do portal que abre o resultado (capítulo abre a primeira página dele).")


class ResultadoBuscaManuais(BaseModel):
    """Resposta do `GET /api/manuais/busca`."""

    itens: list[ResultadoBuscaManual]
