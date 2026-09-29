# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de entrada e saída do Módulo Tarefas.
"""Formatos das rotas `/api/tarefas`."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

StatusTarefa = Literal["a_fazer", "em_andamento", "em_validacao", "concluida"]
PrioridadeTarefa = Literal["baixa", "normal", "alta", "critica"]
AcaoPipeline = Literal["iniciar", "pausar", "entregar", "validar", "devolver", "concluir", "reabrir"]


def _aparar(valor: str) -> str:
    if not valor.strip():
        raise ValueError("não pode ser vazio")
    return valor.strip()


class Pessoa(BaseModel):
    id: int
    nome: str
    login: str = ""


class EquipeResumo(BaseModel):
    id: uuid.UUID
    nome: str


class MarcadorLeitura(BaseModel):
    id: uuid.UUID
    nome: str
    cor: str
    equipe_id: uuid.UUID | None = None


class TarefaResumo(BaseModel):
    """Linha da lista e cartão do Kanban."""
    id: uuid.UUID
    numero: int
    titulo: str
    status: StatusTarefa
    prioridade: PrioridadeTarefa
    prazo: datetime
    prazo_original: datetime
    prorrogacoes: int = Field(..., description="Quantas vezes o prazo foi alterado.")
    atrasada: bool
    equipe: EquipeResumo | None
    responsavel: Pessoa | None
    participantes: int
    marcadores: list[MarcadorLeitura]
    checklist_feitos: int
    checklist_total: int
    carga: float = Field(..., description="Pontos de carga (0 se em validação ou concluída).")
    ordem: int
    atualizado_em: datetime


class Indicadores(BaseModel):
    operacionais: int = Field(..., description="A fazer + em andamento.")
    atrasadas: int
    vencem_hoje: int
    criticas: int
    em_validacao: int
    concluidas: int
    carga: float = Field(..., description="Pontos de carga (prioridade × urgência) das tarefas operacionais.")
    faixa: str


class Contexto(BaseModel):
    tipo: Literal["minhas", "equipe", "pessoa"]
    titulo: str
    equipe_id: uuid.UUID | None = None
    login: str | None = None
    lider: bool = Field(False, description="O usuário lidera o contexto (vê a fila de validação e ações de liderança).")


class ListaTarefas(BaseModel):
    contexto: Contexto
    indicadores: Indicadores
    itens: list[TarefaResumo]


class ItemChecklist(BaseModel):
    id: uuid.UUID
    texto: str
    concluido: bool


class Etapa(BaseModel):
    status: StatusTarefa
    rotulo: str
    em: datetime | None = Field(None, description="Quando a tarefa chegou (pela última vez) a esta etapa.")
    por: str | None = None
    atual: bool
    alcancada: bool


class TarefaDetalhe(TarefaResumo):
    descricao: str
    criado_por: Pessoa | None
    criado_em: datetime
    pessoas: list[Pessoa] = Field(..., description="Responsável e participantes.")
    checklist: list[ItemChecklist]
    etapas: list[Etapa]
    segundos_em_andamento: int
    versao: int
    acoes: list[str] = Field(..., description="Ações permitidas ao usuário agora (a tela mostra só estas).")


class NovaTarefa(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    descricao: str = Field("", max_length=20000)
    prazo: datetime
    prioridade: PrioridadeTarefa = "normal"
    equipe_id: uuid.UUID | None = None
    responsavel_id: int | None = Field(None, description="Vazio: quem cadastra.")
    participantes_ids: list[int] = Field(default_factory=list, max_length=50)
    marcadores_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)

    _t = field_validator("titulo")(lambda cls, v: _aparar(v))


class EdicaoTarefa(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    descricao: str = Field("", max_length=20000)
    prioridade: PrioridadeTarefa
    participantes_ids: list[int] = Field(default_factory=list, max_length=50)
    marcadores_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)
    versao: int | None = Field(None, description="Versão lida (conflito 409 se outra pessoa alterou antes).")

    _t = field_validator("titulo")(lambda cls, v: _aparar(v))


class MudancaPrazo(BaseModel):
    prazo: datetime
    justificativa: str = Field(..., min_length=1, max_length=2000)
    versao: int | None = None


class Movimento(BaseModel):
    acao: AcaoPipeline
    texto: str = Field("", max_length=4000, description="Comentário da entrega; motivo obrigatório para devolver e reabrir.")
    versao: int | None = None


class Transferencia(BaseModel):
    para_id: int
    justificativa: str = Field(..., min_length=1, max_length=2000)
    novo_prazo: datetime | None = None
    versao: int | None = None


class OperacaoChecklist(BaseModel):
    acao: Literal["incluir", "marcar", "remover"]
    texto: str = Field("", max_length=300)
    item_id: uuid.UUID | None = None


class RemocaoEvento(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=1000)


class AnexoLeitura(BaseModel):
    id: uuid.UUID
    nome: str
    tamanho: int
    tipo: str
    removido: bool


class EventoLeitura(BaseModel):
    id: uuid.UUID
    tipo: str
    titulo: str
    texto: str
    dados: dict
    autor: str
    criado_em: datetime
    anexos: list[AnexoLeitura]
    removido: bool
    motivo_remocao: str | None = None


class LinhaDoTempo(BaseModel):
    total: int
    itens: list[EventoLeitura]
    tem_mais: bool


class Reordenacao(BaseModel):
    numeros: list[int] = Field(..., min_length=1, max_length=500, description="Números das tarefas na nova ordem.")


# --- Equipes -------------------------------------------------------------------------------------

class EquipeLeitura(BaseModel):
    id: uuid.UUID
    nome: str
    equipe_pai_id: uuid.UUID | None
    equipe_pai_nome: str | None = None
    dono: Pessoa | None
    lideres: list[Pessoa]
    membros: list[Pessoa]
    indicadores: Indicadores
    lider: bool = Field(..., description="O usuário lidera esta equipe (ou uma acima dela).")
    pode_configurar: bool = Field(..., description="Dono da equipe ou SuperRoot.")


class GravacaoEquipe(BaseModel):
    nome: str = Field(..., min_length=1, max_length=150)
    equipe_pai_id: uuid.UUID | None = None
    lideres_ids: list[int] = Field(default_factory=list, max_length=50)
    membros_ids: list[int] = Field(default_factory=list, max_length=300)

    _n = field_validator("nome")(lambda cls, v: _aparar(v))


class GravacaoMarcador(BaseModel):
    nome: str = Field(..., min_length=1, max_length=60)
    cor: str = Field("#5364ce", pattern=r"^#[0-9a-fA-F]{6}$")

    _n = field_validator("nome")(lambda cls, v: _aparar(v))


class PessoaCarga(BaseModel):
    """Pessoa com a carga atual (seletor de responsável e visão da liderança)."""
    id: int
    nome: str
    login: str
    cargo: str
    carga: float
    faixa: str
    a_fazer: int
    em_andamento: int
    atrasadas: int
    em_validacao: int = 0
    concluidas: int = 0
