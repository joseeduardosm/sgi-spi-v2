# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados da tela Mensageria (e-mail de changelog), exclusiva da conta root.
"""Formatos de entrada e saída das rotas `/api/mensageria`."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.smtp import _email


class RascunhoChangelog(BaseModel):
    """Sugestão do próximo e-mail, montada com as entradas do CHANGELOG ainda não enviadas a todos."""
    assunto: str = Field(..., description="Assunto sugerido. Ex.: `SGI SPI – Novidades de 29/09/2026`.")
    corpo: str = Field(..., description="Texto editável: `## Título`, `- item` (2 espaços por nível) e `**negrito**`.")
    desde: date | None = Field(None, description="Data da última entrada já enviada a todos (nulo: nenhum envio ainda).")
    ate: date | None = Field(None, description="Data da entrada mais recente incluída (nulo: nada novo).")
    datas: list[date] = Field(default_factory=list, description="Datas do CHANGELOG incluídas no rascunho.")
    total_destinatarios: int = Field(..., description="Usuários ativos com e-mail (destino `todos`).")
    setores: list["OpcaoSetorChangelog"] = Field(default_factory=list, description="Setores ativos para o destino `selecionados`.")


class OpcaoSetorChangelog(BaseModel):
    """Setor que pode receber o e-mail (institucional, na hierarquia, ou sistêmico)."""
    id: int
    nome: str
    sistemico: bool
    nivel: int = Field(0, description="Profundidade na hierarquia (para indentar a lista).")


class ConteudoChangelog(BaseModel):
    """Assunto e texto editados na janela."""
    assunto: str = Field(..., min_length=1, max_length=300, description="Assunto do e-mail.")
    corpo: str = Field(..., min_length=1, max_length=50_000, description="Texto no formato do rascunho.")

    @field_validator("assunto", "corpo")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        """Não aceita só espaços."""
        if not valor.strip():
            raise ValueError("não pode ser vazio")
        return valor.strip()


class PreviaChangelog(BaseModel):
    """HTML do e-mail no layout oficial, com o brasão embutido (`data:`), pronto para exibir num `iframe`."""
    html: str = Field(..., description="Documento HTML completo do e-mail.")


class PedidoEnvioChangelog(ConteudoChangelog):
    """Envio do e-mail: a todos os usuários ativos, a usuários e setores escolhidos, ou só a um endereço de teste."""
    destino: Literal["todos", "selecionados", "teste"] = Field(..., description="`todos`, `selecionados` ou `teste`.")
    email_teste: str | None = Field(None, max_length=254, description="Obrigatório quando `destino = teste`.")
    usuarios_ids: list[int] = Field(default_factory=list, max_length=2000, description="Em `selecionados`: usuários escolhidos (1 ou mais).")
    setores_ids: list[int] = Field(default_factory=list, max_length=500,
                                   description="Em `selecionados`: setores sistêmicos ou institucionais (membros, quem tem o setor como Departamento e setores filhos).")
    ate_data: date | None = Field(None, description="`ate` do rascunho: o próximo rascunho começa depois desta data (só em `todos`).")

    @model_validator(mode="after")
    def _teste(self) -> "PedidoEnvioChangelog":
        """O envio de teste exige um e-mail válido."""
        if self.destino == "teste":
            self.email_teste = _email(self.email_teste or "", obrigatorio=True)
        if self.destino == "selecionados" and not (self.usuarios_ids or self.setores_ids):
            raise ValueError("Escolha ao menos um usuário ou um setor.")
        return self


class EnvioChangelogLeitura(BaseModel):
    """Um envio registrado, com o resultado (preenchido quando o envio em segundo plano termina)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assunto: str
    corpo: str
    destino: Literal["todos", "selecionados", "teste"]
    destino_descricao: str | None = Field(None, description="Em `selecionados`: os usuários e setores escolhidos.")
    ate_data: date | None = Field(None, description="Data da entrada mais recente do CHANGELOG incluída (só em `todos`).")
    total: int = Field(..., description="Destinatários.")
    enviados: int = Field(..., description="E-mails aceitos pelo servidor SMTP.")
    falhas: int = Field(..., description="E-mails recusados ou não enviados.")
    erros: str | None = Field(None, description="Um endereço por linha, com o motivo da falha.")
    enviado_por_nome: str
    criado_em: datetime
    concluido_em: datetime | None = Field(None, description="Nulo enquanto o envio está em andamento.")


RascunhoChangelog.model_rebuild()
