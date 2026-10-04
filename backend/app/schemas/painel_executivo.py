# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os formatos (schemas) dos slides do Painel Executivo (contratos, RH e tarefas).
"""Schemas de `/api/painel-executivo`. Os valores monetários seguem o padrão do módulo de contratos (texto com 2 casas)."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.contratos.painel import ExecucaoOrcamentaria, NumerosCarteira
from app.schemas.contratos.tipos import ValorMonetario


class AcessoPainel(BaseModel):
    """Se o usuário logado pode ver o Painel Executivo."""
    pode: bool


class PontoAcumulado(BaseModel):
    """Valores acumulados do exercício até o mês indicado (curva S da execução)."""
    competencia: date
    previsto: ValorMonetario
    medido: ValorMonetario
    pago: ValorMonetario


class FaixaVencimento(BaseModel):
    """Quantos contratos vigentes vencem dentro do prazo."""
    ate_dias: int = Field(..., description="30, 60 ou 90.")
    contratos: int


class RiscoResumo(BaseModel):
    """Um dos contratos de maior risco."""
    contrato_numero: str
    contrato_apelido: str
    empresa: str
    gravidade: str = Field(..., description="`alta` ou `media`.")
    riscos: int = Field(..., description="Quantidade de riscos do contrato.")
    principal: str = Field(..., description="Descrição do risco mais grave.")
    rota: str = Field(..., description="Tela do Angular onde o risco é tratado.")


class SlideContratos(BaseModel):
    """Slide de contratos: números da carteira, execução orçamentária e riscos."""
    gerado_em: datetime
    exercicio: int
    numeros: NumerosCarteira
    execucao: ExecucaoOrcamentaria
    acumulado: list[PontoAcumulado]
    vencimentos: list[FaixaVencimento]
    alertas_altos: int = Field(..., description="Contratos com risco de gravidade alta.")
    alertas_medios: int
    maiores_riscos: list[RiscoResumo]


class PessoaAfastada(BaseModel):
    """Alguém de férias ou licença hoje."""
    nome: str
    setor: str
    tipo: str = Field(..., description="`ferias` ou `licenca_premio`.")
    fim: date


class MesAfastamentos(BaseModel):
    """Pessoas distintas com afastamento (aprovado ou gozado) em cada mês do ano."""
    mes: int = Field(..., ge=1, le=12)
    ferias: int
    licenca_premio: int


class SetorAfastamentos(BaseModel):
    """Dias de afastamento no ano por setor."""
    setor: str
    dias: int
    pessoas: int


class FeriasVencendo(BaseModel):
    """Saldo de férias não agendado com período aquisitivo terminando em até 90 dias."""
    nome: str
    setor: str
    disponivel: int
    periodo_fim: date


class AlertaSetorResumo(BaseModel):
    """Setor com muitas pessoas afastadas ao mesmo tempo."""
    setor: str
    inicio: date
    fim: date
    pessoas: int


class SlideRh(BaseModel):
    """Slide de RH: quem está fora hoje, afastamentos no ano, férias a vencer e alertas de setor."""
    gerado_em: datetime
    ano: int
    afastados_hoje: list[PessoaAfastada]
    por_mes: list[MesAfastamentos]
    por_setor: list[SetorAfastamentos]
    ferias_a_vencer: list[FeriasVencendo]
    alertas_setor: list[AlertaSetorResumo]


class EquipeResumo(BaseModel):
    """Situação das tarefas de uma equipe."""
    equipe: str
    abertas: int
    atrasadas: int
    criticas: int
    carga: float
    faixa: str


class SemanaTarefas(BaseModel):
    """Tarefas criadas e concluídas na semana que começa em `inicio` (segunda-feira)."""
    inicio: date
    criadas: int
    concluidas: int


class SlideTarefas(BaseModel):
    """Slide de tarefas: totais da organização, por equipe e a evolução semanal."""
    gerado_em: datetime
    abertas: int
    atrasadas: int
    vencem_hoje: int
    criticas: int
    em_validacao: int
    concluidas_30_dias: int
    equipes: list[EquipeResumo]
    semanas: list[SemanaTarefas]
