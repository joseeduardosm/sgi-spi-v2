"""Schemas de empresas contratadas e prepostos."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field

from app.schemas.contratos.validadores import normalizar_cnpj, normalizar_cpf


def _aparar(valor: object) -> object:
    return valor.strip() if isinstance(valor, str) else valor


def _nao_vazio(valor: str) -> str:
    if not valor:
        raise ValueError("não pode ser vazio")
    return valor


def _email(valor: str) -> str:
    if valor and ("@" not in valor or valor.startswith("@") or valor.endswith("@") or " " in valor):
        raise ValueError("e-mail inválido")
    return valor


Texto = Annotated[str, BeforeValidator(_aparar)]
TextoObrigatorio = Annotated[str, BeforeValidator(_aparar), AfterValidator(_nao_vazio)]


class GravacaoEmpresa(BaseModel):
    cnpj: Annotated[str, AfterValidator(normalizar_cnpj)] = Field(
        ..., max_length=18, description="CNPJ com ou sem máscara. Gravado só com os 14 dígitos; único.", examples=["12.345.678/0001-95"]
    )
    razao_social: TextoObrigatorio = Field(..., max_length=250)
    nome_fantasia: Texto = Field("", max_length=250)
    endereco: Texto = Field("", max_length=500)
    ativa: bool = Field(True, description="Só empresas ativas aparecem no cadastro de contratos.")


class GravacaoPreposto(BaseModel):
    cpf: Annotated[str, AfterValidator(normalizar_cpf)] = Field(
        ..., max_length=14, description="CPF com ou sem máscara. Gravado só com os 11 dígitos; único na empresa."
    )
    nome: TextoObrigatorio = Field(..., max_length=200)
    telefone: Texto = Field("", max_length=30)
    email: Annotated[str, BeforeValidator(_aparar), AfterValidator(_email)] = Field("", max_length=250)
    cargo: Texto = Field("", max_length=150)
    ativo: bool = True


class LeituraPreposto(BaseModel):
    id: uuid.UUID
    cpf: str = Field(..., description="11 dígitos, sem máscara.")
    nome: str
    telefone: str
    email: str
    cargo: str
    ativo: bool


class ContratoDaEmpresa(BaseModel):
    id: uuid.UUID
    numero: str = Field(..., description="NNN/AAAA")


class ResumoEmpresa(BaseModel):
    id: uuid.UUID
    cnpj: str = Field(..., description="14 dígitos, sem máscara.")
    razao_social: str
    nome_fantasia: str
    endereco: str
    ativa: bool
    prepostos: list[str] = Field(..., description="Nomes dos prepostos.")
    contratos: list[ContratoDaEmpresa]


class PaginaEmpresas(BaseModel):
    itens: list[ResumoEmpresa]
    total: int
    pagina: int
    tamanho_pagina: int


class DetalheEmpresa(BaseModel):
    id: uuid.UUID
    cnpj: str
    razao_social: str
    nome_fantasia: str
    endereco: str
    ativa: bool
    prepostos: list[LeituraPreposto]
    contratos: list[ContratoDaEmpresa]
    criado_em: datetime
    atualizado_em: datetime


class OpcaoEmpresa(BaseModel):
    """Forma reduzida para o seletor de empresa do contrato."""

    id: uuid.UUID
    cnpj: str
    razao_social: str
    nome_fantasia: str
    ativa: bool
