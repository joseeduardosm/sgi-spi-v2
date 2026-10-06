# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados da assinatura de e-mail.
"""Formatos de entrada e saída da assinatura de e-mail (`/api/assinatura-email`)."""

import re

from pydantic import BaseModel, Field, field_validator

from app.schemas.usuarios import PADRAO_EMAIL


class DadosAssinatura(BaseModel):
    """Dados que aparecem na assinatura. Valem só para gerar a imagem: nada é gravado no perfil."""

    nome_completo: str = Field("", max_length=220)
    cargo: str = Field("", max_length=180)
    departamento: str = Field("", max_length=180)
    email: str = Field("", max_length=254)
    ramal: str = Field("", max_length=20, description="Só dígitos e hífen; o prefixo do telefone vem da configuração.")
    celular: str = Field("", max_length=30)
    andar: str = Field("", max_length=30, description="`Subsolo` ou `1` a `13`.")
    lado: str = Field("", max_length=10, description="`A` ou `B`.")
    incluir_celular: bool = Field(False, description="Mostra o celular na assinatura.")
    incluir_andar_lado: bool = Field(False, description="Mostra o andar e o lado (ex.: 5º andar · Lado B).")

    @field_validator("nome_completo", "cargo", "departamento", "email", "ramal", "celular", "andar", "lado")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        return valor.strip()

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        if valor and not PADRAO_EMAIL.match(valor):
            raise ValueError("e-mail inválido")
        return valor

    @field_validator("ramal")
    @classmethod
    def _ramal(cls, valor: str) -> str:
        if valor and not re.fullmatch(r"[0-9\-]+", valor):
            raise ValueError("o ramal só pode ter dígitos e hífen")
        return valor

    @field_validator("celular")
    @classmethod
    def _celular(cls, valor: str) -> str:
        if valor and not re.fullmatch(r"[0-9 ()+\-]+", valor):
            raise ValueError("o celular só pode ter dígitos, espaço, parênteses, + e hífen")
        return valor


class LeituraDadosAssinatura(DadosAssinatura):
    """Dados em vigor do perfil, para pré-preencher o formulário."""

    telefone_prefixo: str = Field("", description="Prefixo do telefone da SPI; o ramal vem depois dele (configuração `ASSINATURA_TELEFONE_PREFIXO`).")
    faltando: list[str] = Field(default_factory=list, description="Campos obrigatórios que o perfil ainda não tem (nome, cargo, e-mail).")


class PreviaAssinatura(BaseModel):
    png_base64: str = Field(..., description="PNG do modelo PPTX (hoje 1765×492; exibir a 564 px de largura) em base64.")
    html: str = Field(..., description="Assinatura em HTML (a imagem do modelo em uma tabela), para colar no Outlook ou no webmail.")
    avisos: list[str] = Field(default_factory=list, description="Texto abreviado ou campo ausente na imagem.")
