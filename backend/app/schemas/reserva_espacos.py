# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados da Reserva de Espaços (/api/reserva-espacos).
"""Formatos de entrada e saída da Reserva de Espaços."""

from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, Field

StatusReserva = Literal["AGUARDANDO_APROVACAO", "DEFERIDA", "INDEFERIDA", "CANCELADA"]
Recorrencia = Literal["nenhuma", "diaria", "semanal", "quinzenal", "mensal"]
EscopoCancelamento = Literal["ocorrencia", "serie", "periodo"]


class GravacaoEspaco(BaseModel):
    nome: str = Field(..., min_length=1, max_length=120, description="Nome do espaço; único sem diferenciar maiúsculas.")
    localizacao: str = Field("", max_length=200, description="Onde fica (ex.: 2º andar > Lado A).")
    cor: str = Field("#0b5cad", pattern=r"^#[0-9a-fA-F]{6}$", description="Cor hexadecimal usada na agenda.")
    capacidade: int | None = Field(None, ge=1, le=10000, description="Número de lugares (opcional).")
    equipamentos: str = Field("", max_length=2000, description="Equipamentos disponíveis (projetor, TV, videoconferência…).")
    descricao: str = Field("", max_length=2000)
    ativo: bool = True


class EspacoLeitura(GravacaoEspaco):
    id: int


class GravacaoReserva(BaseModel):
    espaco_id: int
    data: date
    hora_inicio: time
    hora_fim: time
    titulo: str = Field(..., min_length=1, max_length=200)
    observacoes: str = Field("", max_length=4000)
    participantes: int | None = Field(None, ge=1, le=10000, description="Quantidade de participantes (confrontada com a capacidade, só como aviso).")
    recorrencia: Recorrencia = "nenhuma"
    recorrencia_ate: date | None = Field(None, description="Obrigatória quando há recorrência: última data possível.")
    responsavel_id: int | None = Field(None, description="Só na reserva predefinida: usuário responsável.")
    responsavel_nome: str = Field("", max_length=200, description="Só na reserva predefinida: nome digitado quando o responsável não é usuário.")


class EdicaoReserva(BaseModel):
    espaco_id: int
    data: date
    hora_inicio: time
    hora_fim: time
    titulo: str = Field(..., min_length=1, max_length=200)
    observacoes: str = Field("", max_length=4000)
    participantes: int | None = Field(None, ge=1, le=10000)


class EventoLeitura(BaseModel):
    id: int
    tipo: str
    usuario_nome: str
    detalhes: dict[str, Any] | None = None
    criado_em: datetime


class ReservaLeitura(BaseModel):
    id: int
    espaco_id: int
    espaco_nome: str
    espaco_cor: str
    data: date
    hora_inicio: time
    hora_fim: time
    titulo: str
    responsavel_id: int | None
    responsavel_nome: str
    solicitante_id: int | None
    solicitante_nome: str
    observacoes: str
    participantes: int | None
    status: StatusReserva
    fiscal_nome: str
    justificativa: str
    serie_id: str | None
    ocorrencias_serie: int = Field(1, description="Total de ocorrências da série (1 quando não é recorrente).")
    pode_editar: bool = False
    pode_cancelar: bool = False
    pode_analisar: bool = False
    criado_em: datetime


class ReservaDetalhe(ReservaLeitura):
    eventos: list[EventoLeitura]
    serie: list[ReservaLeitura] = Field(default_factory=list, description="Demais ocorrências da série, em ordem de data.")


class ListaReservas(BaseModel):
    total: int
    itens: list[ReservaLeitura]


class ResultadoSolicitacao(BaseModel):
    reservas: list[ReservaLeitura]
    avisos: list[str] = Field(default_factory=list, description="Avisos que não impedem a reserva (ex.: outra solicitação pendente no mesmo horário).")


class Analise(BaseModel):
    decisao: Literal["deferir", "indeferir"]
    justificativa: str = Field("", max_length=4000, description="Obrigatória ao indeferir.")


class Cancelamento(BaseModel):
    escopo: EscopoCancelamento = "ocorrencia"
    motivo: str = Field(..., min_length=1, max_length=4000)
    de: date | None = Field(None, description="Início do período (escopo `periodo`).")
    ate: date | None = Field(None, description="Fim do período (escopo `periodo`).")


class ContextoReserva(BaseModel):
    eh_fiscal: bool
    espacos: list[EspacoLeitura]


class Fiscal(BaseModel):
    id: int
    nome: str
    login: str


class ConfiguracaoLeitura(BaseModel):
    hora_abertura: time
    hora_fechamento: time
    antecedencia_minima_horas: int = Field(..., ge=0, le=720)
    duracao_maxima_horas: int = Field(..., ge=0, le=24)
    fiscais: list[Fiscal]


class GravacaoConfiguracao(BaseModel):
    hora_abertura: time
    hora_fechamento: time
    antecedencia_minima_horas: int = Field(0, ge=0, le=720)
    duracao_maxima_horas: int = Field(0, ge=0, le=24)
    fiscais_ids: list[int] = Field(default_factory=list)


class MesPainel(BaseModel):
    mes: int
    rotulo: str
    total: int


class OcupacaoPainel(BaseModel):
    espaco: str
    cor: str
    horas: float
    reservas: int
    ocupacao_percentual: float


class PessoaPainel(BaseModel):
    nome: str
    total: int


class PainelReservas(BaseModel):
    ano: int
    mes: int
    total: int
    deferidas: int
    indeferidas: int
    aguardando: int
    canceladas: int
    espacos_ativos: int
    media_por_dia: float
    por_mes: list[MesPainel]
    ocupacao: list[OcupacaoPainel]
    pessoas: list[PessoaPainel]
