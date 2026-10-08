# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos atalhos fixos da barra lateral (leitura para todos e cadastro para quem gerencia).
"""Schemas de `/api/atalhos`."""

from pydantic import BaseModel, Field, field_validator


class LeituraAtalho(BaseModel):
    """Um atalho (interno: rota do SGI; externo: endereço http/https)."""

    id: int
    categoria_id: int
    titulo: str
    url: str
    externo: bool = Field(..., description="Verdadeiro quando a URL é um endereço externo (`http://` ou `https://`).")
    nova_aba: bool
    ordem: int
    ativo: bool


class LeituraCategoriaAtalho(BaseModel):
    """Categoria com seus atalhos (na leitura comum, só os ativos)."""

    id: int
    nome: str
    ordem: int
    ativo: bool
    atalhos: list[LeituraAtalho]


class ListaAtalhos(BaseModel):
    """Atalhos fixos organizados por categoria, na ordem de exibição."""

    categorias: list[LeituraCategoriaAtalho]


class GravacaoCategoriaAtalho(BaseModel):
    """Corpo de criação e alteração de categoria."""

    nome: str = Field(..., min_length=1, max_length=80)
    ordem: int = Field(0, ge=0, le=9999, description="Menor aparece primeiro.")
    ativo: bool = True

    @field_validator("nome")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("informe o nome da categoria")
        return valor


class GravacaoAtalho(BaseModel):
    """Corpo de criação e alteração de atalho."""

    categoria_id: int
    titulo: str = Field(..., min_length=1, max_length=80)
    url: str = Field(..., min_length=1, max_length=500, description="Rota interna (começa por `/`, ex.: `/contratos`) ou endereço externo (`https://…`).")
    nova_aba: bool | None = Field(None, description="Abrir em nova aba. Em branco: externos abrem em nova aba; internos, na mesma.")
    ordem: int = Field(0, ge=0, le=9999)
    ativo: bool = True

    @field_validator("titulo")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("informe o título do atalho")
        return valor

    @field_validator("url")
    @classmethod
    def _destino(cls, valor: str) -> str:
        """Só rota interna (`/…`, sem `//`) ou http(s); `javascript:` e outros esquemas são recusados."""
        valor = valor.strip()
        if valor.startswith("/") and not valor.startswith("//") and "://" not in valor:
            return valor
        if valor.lower().startswith(("http://", "https://")) and len(valor.split("://", 1)[1]) > 3 and " " not in valor:
            return valor
        raise ValueError("informe uma rota do sistema (começando por \"/\") ou um endereço http:// ou https://")
