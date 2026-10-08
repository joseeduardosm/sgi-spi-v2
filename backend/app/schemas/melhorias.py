# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de entrada e saída do Módulo Melhorias.
"""Formatos das rotas `/api/melhorias`.

O autor vê a própria sugestão com a situação e a resposta pública (`SugestaoAutor`); a triagem vê também a observação
interna e o histórico (`SugestaoTriagem`).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.sla import SlaItem
from app.schemas.tarefas import PrioridadeTarefa

SituacaoSugestao = Literal["nova", "em_analise", "aceita", "recusada", "concluida"]
MAXIMO_TEXTO = 4000


class GravacaoSugestao(BaseModel):
    """Sugestão enviada pelo botão flutuante (campo `dados` do multipart)."""

    texto: str = Field(..., min_length=1, max_length=MAXIMO_TEXTO, description="Proposta de melhoria.")
    tela: str = Field("", max_length=1000, description="Rota em que o usuário estava (ex.: `/contratos/…/execucao/2026-02`).")

    @field_validator("texto")
    @classmethod
    def _texto(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("Descreva a melhoria.")
        return valor.strip()

    @field_validator("tela")
    @classmethod
    def _tela(cls, valor: str) -> str:
        return valor.strip()


class PrintLeitura(BaseModel):
    """Print anexado (a `url` baixa o arquivo com o token)."""

    id: uuid.UUID
    nome: str
    tamanho: int
    url: str


class SugestaoAutor(BaseModel):
    """O que o autor vê da própria sugestão (sem a observação interna)."""

    id: uuid.UUID
    numero: int
    texto: str
    tela: str
    modulo: str
    situacao: SituacaoSugestao
    resposta_publica: str
    criado_em: datetime
    atualizado_em: datetime | None
    prints: list[PrintLeitura]


class EventoLeitura(BaseModel):
    descricao: str
    situacao_anterior: str
    situacao_nova: str
    autor_nome: str
    criado_em: datetime


class SugestaoTriagem(SugestaoAutor):
    """Visão completa da triagem."""

    autor_id: int | None
    autor_nome: str
    autor_login: str
    observacao_interna: str
    atualizado_por_nome: str
    tarefa_numero: int | None = Field(None, description="Tarefa criada a partir da sugestão (Módulo Tarefas).")
    sla: SlaItem | None = Field(None, description="SLA da triagem: resposta (primeira mudança de situação) e resolução (conclusão ou recusa), em dias úteis.")
    eventos: list[EventoLeitura]


class PaginaSugestoesAutor(BaseModel):
    itens: list[SugestaoAutor]
    total: int
    pagina: int
    tamanho: int


class PaginaSugestoesTriagem(BaseModel):
    itens: list[SugestaoTriagem]
    total: int
    pagina: int
    tamanho: int
    totais: dict[str, int] = Field(..., description="Quantidade por situação (com os demais filtros aplicados).")
    modulos: list[str] = Field(..., description="Módulos com sugestões, para o filtro.")


class TratamentoSugestao(BaseModel):
    """Triagem: situação, resposta ao autor e observação interna."""

    situacao: SituacaoSugestao
    resposta_publica: str = Field("", max_length=MAXIMO_TEXTO, description="Vai ao autor (aviso na caixa de Mensagens).")
    observacao_interna: str = Field("", max_length=12000, description="Só a triagem vê.")


class ConversaoTarefa(BaseModel):
    """Dados da tarefa criada a partir da sugestão."""

    titulo: str = Field(..., min_length=1, max_length=200)
    prazo: datetime
    prioridade: PrioridadeTarefa = "normal"
    equipe_id: uuid.UUID | None = None
    responsavel_id: int | None = Field(None, description="Vazio: quem converte.")


class PodeTriar(BaseModel):
    """Se o usuário logado faz a triagem (a tela mostra ou esconde a aba)."""

    triagem: bool
