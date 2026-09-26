# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados do painel de contratos.
"""Schemas do painel de contratos (`/contratos/painel`).

O painel tem quatro blocos: minhas pendências (tarefas do usuário), alertas de risco da
carteira, execução orçamentária do exercício e números da carteira.
"""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.contratos.tipos import ValorMonetario

# Tipos de pendência (cada um aponta para uma etapa ou tela onde o usuário precisa agir)
TipoPendencia = Literal[
    "medicao", "ciencia_medicao", "avaliacao", "ciencia_ateste", "nota_fiscal", "retencao", "cadin", "checklist", "consolidado", "ordem_bancaria",
    "prorrogacao", "reajuste", "alteracao", "ciencia_alteracao", "base_execucao",
]
# Tipos de risco verificados em todos os contratos
TipoRisco = Literal["a_vencer_sem_prorrogacao", "vigencia_maxima", "reajuste_pendente", "empenho_insuficiente", "pagamento_vencido",
                    "pagamento_vencendo", "competencias_atrasadas"]


class Pendencia(BaseModel):
    """Uma tarefa do usuário logado, com o link direto para a tela onde ela é resolvida."""
    tipo: TipoPendencia
    contrato_id: uuid.UUID
    contrato_numero: str
    contrato_apelido: str
    descricao: str
    rota: str = Field(..., description="Caminho da tela no Angular (ex.: `/contratos/<id>/execucao/2026-05`).")
    desde: date | None = Field(None, description="Data de referência (fim do período, vencimento…) para ordenar por urgência.")


class Risco(BaseModel):
    """Um risco detectado em um contrato."""
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
    """Valores de um mês do exercício (alimenta o gráfico previsto × medido × pago)."""
    competencia: date
    previsto: ValorMonetario
    medido: ValorMonetario
    pago: ValorMonetario


class ExecucaoOrcamentaria(BaseModel):
    """Execução orçamentária do exercício: totais por mês e situação dos empenhos."""
    exercicio: int
    meses: list[MesExecucao]
    total_previsto: ValorMonetario
    total_medido: ValorMonetario
    total_pago: ValorMonetario
    empenhado: ValorMonetario = Field(..., description="Soma das NEs dos contratos filtrados.")
    consumido: ValorMonetario
    saldo_empenho: ValorMonetario


class NumerosCarteira(BaseModel):
    """Contagens e somas gerais da carteira de contratos."""
    contratos_ativos: int
    contratos_a_vencer: int
    contratos_encerrados: int
    valor_global_ativos: ValorMonetario
    base_mensal_ativos: ValorMonetario


class OpcaoFiltro(BaseModel):
    """Opção de um filtro (empresa ou contrato) no topo do painel."""
    id: uuid.UUID
    rotulo: str


class Painel(BaseModel):
    """Resposta completa do `GET /api/contratos/painel`."""
    hoje: date
    minhas_pendencias: list[Pendencia]
    alertas: list[AlertasContrato] = Field(..., description="Riscos agrupados por contrato, mais graves primeiro.")
    execucao: ExecucaoOrcamentaria
    numeros: NumerosCarteira
    empresas: list[OpcaoFiltro] = Field(..., description="Opções do filtro de empresa.")
    contratos: list[OpcaoFiltro] = Field(..., description="Opções do filtro de contrato.")
