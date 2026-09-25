# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados do painel de contratos.
"""Schemas do painel de contratos (`/contratos/painel`)."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.contratos.tipos import ValorMonetario

TipoPendencia = Literal[
    "medicao", "ciencia_medicao", "avaliacao", "ciencia_ateste", "nota_fiscal", "cadin", "checklist", "consolidado", "ordem_bancaria",
    "prorrogacao", "reajuste", "alteracao", "ciencia_alteracao", "base_execucao",
]
TipoRisco = Literal["a_vencer_sem_prorrogacao", "vigencia_maxima", "reajuste_pendente", "empenho_insuficiente", "pagamento_vencido",
                    "pagamento_vencendo", "competencias_atrasadas"]


class Pendencia(BaseModel):
    tipo: TipoPendencia
    contrato_id: uuid.UUID
    contrato_numero: str
    contrato_apelido: str
    descricao: str
    rota: str = Field(..., description="Caminho da tela no Angular (ex.: `/contratos/<id>/execucao/2026-05`).")
    desde: date | None = Field(None, description="Data de referência (fim do período, vencimento…) para ordenar por urgência.")


class Risco(BaseModel):
    tipo: TipoRisco
    gravidade: Literal["alta", "media"]
    descricao: str
    rota: str = Field(..., description="Tela onde o risco é tratado.")
    data: date | None = Field(None, description="Data de referência (vencimento, fim da vigência…).")
    valor: ValorMonetario | None = Field(None, description="Valor em risco, quando se aplica (ex.: falta de empenho).")


class AlertasContrato(BaseModel):
    """Riscos de um contrato. Só entram riscos; as tarefas do dia a dia ficam em "Minhas pendências"."""

    contrato_id: uuid.UUID
    contrato_numero: str
    contrato_apelido: str
    empresa: str
    gravidade: Literal["alta", "media"] = Field(..., description="A maior gravidade entre os riscos do contrato.")
    riscos: list[Risco]


class MesExecucao(BaseModel):
    competencia: date
    previsto: ValorMonetario
    medido: ValorMonetario
    pago: ValorMonetario


class ExecucaoOrcamentaria(BaseModel):
    exercicio: int
    meses: list[MesExecucao]
    total_previsto: ValorMonetario
    total_medido: ValorMonetario
    total_pago: ValorMonetario
    empenhado: ValorMonetario = Field(..., description="Soma das NEs dos contratos filtrados.")
    consumido: ValorMonetario
    saldo_empenho: ValorMonetario


class NumerosCarteira(BaseModel):
    contratos_ativos: int
    contratos_a_vencer: int
    contratos_encerrados: int
    valor_global_ativos: ValorMonetario
    base_mensal_ativos: ValorMonetario


class OpcaoFiltro(BaseModel):
    id: uuid.UUID
    rotulo: str


class Painel(BaseModel):
    hoje: date
    minhas_pendencias: list[Pendencia]
    alertas: list[AlertasContrato] = Field(..., description="Riscos agrupados por contrato, mais graves primeiro.")
    execucao: ExecucaoOrcamentaria
    numeros: NumerosCarteira
    empresas: list[OpcaoFiltro] = Field(..., description="Opções do filtro de empresa.")
    contratos: list[OpcaoFiltro] = Field(..., description="Opções do filtro de contrato.")
