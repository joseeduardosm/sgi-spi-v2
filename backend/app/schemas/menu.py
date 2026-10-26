# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato da configuração do menu lateral (leitura para todos e gravação para quem gerencia).
"""Schemas de `/api/menu`."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MAXIMO_NOS = 200


class NoMenu(BaseModel):
    """Um nó do menu: um módulo do sistema (só posição, nome e visibilidade), um grupo ou um link criado pelo administrador."""

    id: str = Field(..., min_length=1, max_length=60, pattern=r"^[a-z0-9][a-z0-9_-]*$", description="Identificador estável. Módulos usam o `id` do item do código (ex.: `contratos`); grupos e links criados usam `g-…` e `l-…`.")
    tipo: Literal["modulo", "grupo", "link"]
    rotulo: str | None = Field(None, max_length=80, description="Nome exibido. Obrigatório em grupos e links; em módulos, vazio mantém o nome padrão.")
    pai_id: str | None = Field(None, description="`id` do grupo onde o nó fica; vazio = primeiro nível. No máximo dois níveis.")
    oculto: bool = Field(False, description="Oculto no menu e na busca global (a rota e a ACL continuam valendo).")
    url: str | None = Field(None, max_length=500, description="Só em links: rota interna (`/ramais`) ou endereço `http(s)://`.")
    nova_aba: bool | None = Field(None, description="Só em links: abre em nova aba (padrão: externos sim, internos não).")

    @field_validator("rotulo", "url")
    @classmethod
    def _aparar(cls, valor: str | None) -> str | None:
        valor = (valor or "").strip()
        return valor or None

    @model_validator(mode="after")
    def _coerente(self) -> "NoMenu":
        if self.tipo in ("grupo", "link") and not self.rotulo:
            raise ValueError("Informe o nome do grupo ou do link.")
        if self.tipo == "link":
            if not self.url:
                raise ValueError("Informe o endereço do link.")
            if not (self.url.startswith("/") and not self.url.startswith("//") or self.url.lower().startswith(("http://", "https://"))):
                raise ValueError("O endereço deve ser uma rota interna (começa por /) ou um endereço http(s)://.")
        elif self.url:
            raise ValueError("Só links têm endereço.")
        return self


class GravacaoMenu(BaseModel):
    """Configuração completa do menu (substitui a anterior)."""

    itens: list[NoMenu] = Field(..., max_length=MAXIMO_NOS)

    @model_validator(mode="after")
    def _estrutura(self) -> "GravacaoMenu":
        ids = [n.id for n in self.itens]
        if len(set(ids)) != len(ids):
            raise ValueError("Há itens repetidos no menu.")
        por_id = {n.id: n for n in self.itens}
        for no in self.itens:
            if no.pai_id is None:
                continue
            pai = por_id.get(no.pai_id)
            if pai is None or pai.id == no.id:
                raise ValueError(f"O grupo de \"{no.rotulo or no.id}\" não existe no menu.")
            if pai.tipo == "link":
                raise ValueError("Um link não pode conter outros itens.")
            if pai.pai_id is not None:
                raise ValueError("O menu aceita no máximo dois níveis (grupo e itens dentro dele).")
        return self


class LeituraMenu(BaseModel):
    """Configuração efetiva do menu."""

    itens: list[NoMenu]
    padrao: bool = Field(..., description="Verdadeiro quando nada foi configurado: vale o menu padrão do código.")
    atualizado_por_nome: str = ""
    atualizado_em: datetime | None = None
