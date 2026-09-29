# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados do Módulo RH (cadastro validado pela CGP, férias e licença-prêmio).
"""Schemas do Módulo RH (`/api/rh`)."""

import uuid
import re
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TipoAfastamento = Literal["ferias", "licenca_premio"]
StatusAfastamento = Literal["pendente", "aprovado", "recusado", "cancelado", "gozado"]


class PapeisRh(BaseModel):
    cgp: bool = Field(..., description="Coordenadoria de Gestão de Pessoas (ou SuperRoot): acesso total ao RH.")
    autorizador: bool = Field(..., description="Autoriza férias/LP de alguém (ou é substituto de um autorizador).")


# --- Cadastro -----------------------------------------------------------------------------------

class AlteracaoLeitura(BaseModel):
    id: uuid.UUID
    campo: str
    rotulo: str
    valor_anterior: str | None
    valor_anterior_rotulo: str
    valor_proposto: str | None
    valor_proposto_rotulo: str
    status: Literal["pendente", "validada", "recusada", "substituida"]
    solicitada_em: datetime
    solicitada_por_nome: str
    analisada_por_nome: str | None
    analisada_em: datetime | None
    justificativa: str | None
    valor_corrigido: str | None
    valor_corrigido_rotulo: str | None


class UsuarioPendente(BaseModel):
    usuario_id: int
    nome: str
    login: str
    departamento: str
    alteracoes: list[AlteracaoLeitura]


class Recusa(BaseModel):
    justificativa: str = Field(..., min_length=1, max_length=2000)
    valor_corrigido: str | None = Field(None, max_length=500, description="Valor que passa a valer (superior imediato: id; data: AAAA-MM-DD).")


class PeriodoLeitura(BaseModel):
    """Período aquisitivo de férias (12 meses)."""
    inicio: date
    fim: date
    dias_creditados: int
    usado: int = Field(..., description="Dias de férias (pendentes, aprovadas, gozadas) que começam no período.")
    disponivel: int
    dias_expirados: int | None = Field(None, description="Saldo que expirou no fim do período (só nos encerrados).")
    origem: Literal["automatico", "ajuste_cgp"]
    vigente: bool


class DadosFuncionaisLeitura(BaseModel):
    autorizador_id: int | None
    autorizador_nome: str | None
    autorizador_sugerido_id: int | None = Field(..., description="Sugestão: o superior imediato em vigor.")
    substituto_id: int | None
    substituto_nome: str | None
    sem_superior: bool
    inicio_periodo_aquisitivo: str | None = Field(..., description="Início do período aquisitivo de férias, `DD/MM` (repete todo ano).")
    periodos: list[PeriodoLeitura] = Field(default_factory=list, description="Períodos aquisitivos, do mais recente para o mais antigo.")
    exercicio: int | None = Field(..., description="Exercício (ano civil) do saldo de licença-prêmio.")
    saldo_lp_dias: int
    jornada_semanal_horas: int | None = Field(None, description="Jornada de trabalho em horas semanais (ex.: 40).")
    regime_plantao: bool = False
    horario_trabalho_inicio: str | None = Field(None, description="`HH:MM` (ex.: `09:00`).")
    horario_trabalho_fim: str | None = Field(None, description="`HH:MM` (ex.: `18:00`).")
    horario_estudante: bool = False
    intervalo_inicio: str | None = Field(None, description="Intervalo de almoço e descanso, `HH:MM` (ex.: `12:00`).")
    intervalo_fim: str | None = Field(None, description="`HH:MM` (ex.: `13:00`).")
    rg_cin: str | None = Field(None, description="Nº do RG ou da CIN (ex.: `12.345.678-9`).")
    rs_pv: str | None = Field(None, description="Nº do RS/PV (ex.: `1.234.567/8`).")
    atualizado_por_nome: str | None
    atualizado_em: datetime | None


class GravacaoDadosFuncionais(BaseModel):
    autorizador_id: int | None = None
    substituto_id: int | None = Field(None, description="Aprova no lugar deste usuário (como autorizador) quando ele estiver afastado.")
    sem_superior: bool = Field(False, description="Topo da hierarquia: dispensado de informar superior imediato.")
    inicio_periodo_aquisitivo: str | None = Field(None, max_length=5, description="`DD/MM` (ex.: `15/03`); vazio = não informado.")
    exercicio: int | None = Field(None, ge=2000, le=2100, description="Exercício do saldo de licença-prêmio.")
    saldo_lp_dias: int = Field(0, ge=0, le=365)
    jornada_semanal_horas: int | None = Field(None, ge=1, le=80, description="Horas semanais (ex.: 40).")
    regime_plantao: bool = Field(False, description="Regime de plantão.")
    horario_trabalho_inicio: time | None = Field(None, description="Início do horário de trabalho, `HH:MM`.")
    horario_trabalho_fim: time | None = Field(None, description="Fim do horário de trabalho, `HH:MM` (pode ser menor que o início em plantão noturno).")
    horario_estudante: bool = Field(False, description="Horário de estudante.")
    intervalo_inicio: time | None = Field(None, description="Início do intervalo de almoço e descanso, `HH:MM`.")
    intervalo_fim: time | None = Field(None, description="Fim do intervalo, `HH:MM` (depois do início).")
    rg_cin: str | None = Field(None, max_length=30, description="Nº do RG ou da CIN: dígitos, letras, ponto, hífen, barra e espaço.")
    rs_pv: str | None = Field(None, max_length=30, description="Nº do RS/PV: dígitos, letras, ponto, hífen, barra e espaço.")

    @field_validator("rg_cin", "rs_pv")
    @classmethod
    def _documento(cls, valor: str | None) -> str | None:
        """Apara; vazio vira nulo; só caracteres de número de documento."""
        valor = (valor or "").strip()
        if not valor:
            return None
        if not re.fullmatch(r"[0-9A-Za-z./\- ]+", valor):
            raise ValueError("use só dígitos, letras, ponto, hífen, barra e espaço")
        return valor

    @field_validator("horario_trabalho_inicio", "horario_trabalho_fim", "intervalo_inicio", "intervalo_fim")
    @classmethod
    def _sem_segundos(cls, valor: time | None) -> time | None:
        """Guarda só hora e minuto."""
        return valor.replace(second=0, microsecond=0) if valor else None

    @model_validator(mode="after")
    def _pares(self) -> "GravacaoDadosFuncionais":
        """Horário e intervalo: início e fim juntos; o intervalo termina depois de começar."""
        if (self.horario_trabalho_inicio is None) != (self.horario_trabalho_fim is None):
            raise ValueError("Informe o início e o fim do horário de trabalho (ou nenhum dos dois).")
        if (self.intervalo_inicio is None) != (self.intervalo_fim is None):
            raise ValueError("Informe o início e o fim do intervalo (ou nenhum dos dois).")
        if self.horario_trabalho_inicio is not None and self.horario_trabalho_inicio == self.horario_trabalho_fim:
            raise ValueError("O horário de trabalho precisa terminar em hora diferente do início.")
        if self.intervalo_inicio is not None and self.intervalo_fim <= self.intervalo_inicio:
            raise ValueError("O intervalo precisa terminar depois de começar.")
        return self


class AjustePeriodo(BaseModel):
    """Ajuste da CGP nos dias creditados do período aquisitivo vigente (ex.: férias gozadas antes do sistema)."""
    dias_creditados: int = Field(..., ge=0, le=365)


class CadastroRh(BaseModel):
    """Visão da CGP sobre o cadastro de um usuário."""
    usuario_id: int
    nome: str
    login: str
    perfil: dict[str, str | None] = Field(..., description="Valores em vigor, por campo (para exibir).")
    pendentes: list[AlteracaoLeitura]
    historico: list[AlteracaoLeitura]
    funcionais: DadosFuncionaisLeitura


# --- Afastamentos -------------------------------------------------------------------------------

class PedidoAfastamento(BaseModel):
    tipo: TipoAfastamento
    inicio: date
    fim: date


class Decisao(BaseModel):
    justificativa: str | None = Field(None, max_length=2000, description="Obrigatória na recusa.")


class EventoLeitura(BaseModel):
    de: str | None
    para: str
    autor_nome: str
    justificativa: str | None
    ocorrido_em: datetime


class AfastamentoLeitura(BaseModel):
    id: uuid.UUID
    usuario_id: int
    nome: str
    setor: str
    tipo: TipoAfastamento
    inicio: date
    fim: date
    dias: int
    exercicio: int
    status: StatusAfastamento
    solicitado_em: datetime
    decidido_por_nome: str | None
    decidido_em: datetime | None
    justificativa: str | None
    substitui_id: uuid.UUID | None
    pode_decidir: bool = False
    pode_alterar: bool = False
    eventos: list[EventoLeitura] = Field(default_factory=list)


class SaldoLeitura(BaseModel):
    saldo: int
    usado: int = Field(..., description="Dias de pedidos pendentes, aprovados e gozados no exercício.")
    disponivel: int


class PeriodoAtual(BaseModel):
    """Período aquisitivo vigente, com as datas do aviso de expiração."""
    inicio: date
    fim: date
    dias_creditados: int
    usado: int
    disponivel: int
    expira_em_dias: int = Field(..., description="Dias até o fim do período (inclusive).")
    data_limite_inicio: date | None = Field(None, description="Último dia para começar as férias usando todo o saldo.")
    data_limite_pedido: date | None = Field(None, description="Último dia para pedir, considerando a antecedência mínima.")
    alerta_expiracao: bool = Field(..., description="Já está na janela de aviso (saldo não agendado prestes a expirar).")


class ProximoPeriodo(BaseModel):
    inicio: date
    fim: date
    dias_creditados_previstos: int
    usado: int


class FeriadoLeitura(BaseModel):
    """Feriado ou ponto facultativo cadastrado pela CGP."""
    id: uuid.UUID
    data: date
    descricao: str
    tipo: Literal["feriado", "ponto_facultativo"]
    abrangencia: Literal["nacional", "estadual", "municipal"]
    atualizado_por_nome: str | None = None
    atualizado_em: datetime | None = None


class CompetenciaFolha(BaseModel):
    """Mês disponível para a folha de ponto."""
    valor: str = Field(..., description="`AAAA-MM`.")
    rotulo: str = Field(..., description="Ex.: `Outubro/2026`.")
    atual: bool = Field(..., description="Mês corrente (pré-selecionado).")


class GravacaoFeriado(BaseModel):
    """Cadastro ou alteração de feriado ou ponto facultativo (uma data só pode ter um)."""
    data: date
    descricao: str = Field(..., min_length=1, max_length=200, description="Ex.: `Nossa Senhora Aparecida`.")
    tipo: Literal["feriado", "ponto_facultativo"]
    abrangencia: Literal["nacional", "estadual", "municipal"] = "nacional"

    @field_validator("descricao")
    @classmethod
    def _descricao(cls, valor: str) -> str:
        """Não aceita só espaços."""
        if not valor.strip():
            raise ValueError("não pode ser vazio")
        return valor.strip()


class MeusAfastamentos(BaseModel):
    exercicio: int
    saldos: dict[str, SaldoLeitura] = Field(..., description="`ferias`: período aquisitivo vigente; `licenca_premio`: exercício (ano civil).")
    periodo_vigente: PeriodoAtual | None = Field(None, description="Nulo se a CGP ainda não informou o início do período aquisitivo.")
    proximo_periodo: ProximoPeriodo | None = None
    afastamentos: list[AfastamentoLeitura]
    parametros: "ParametrosLeitura"
    feriados: list[FeriadoLeitura] = Field(default_factory=list, description="Feriados e pontos facultativos do exercício (calendário).")


class AlertaSetor(BaseModel):
    setor: str
    inicio: date
    fim: date
    pessoas: int


class OpcaoPessoa(BaseModel):
    id: int
    nome: str
    setor: str


class OpcaoSetor(BaseModel):
    id: int
    nome: str
    nivel: int


class FeriasAVencer(BaseModel):
    usuario_id: int
    nome: str
    setor: str
    periodo_inicio: date
    periodo_fim: date
    disponivel: int
    data_limite_pedido: date | None


class PainelAfastamentos(BaseModel):
    visao: Literal["mensal", "anual"]
    inicio: date
    fim: date
    cgp: bool
    periodos: list[AfastamentoLeitura]
    alertas: list[AlertaSetor]
    pessoas: list[OpcaoPessoa]
    setores: list[OpcaoSetor]
    ferias_a_vencer: list[FeriasAVencer] = Field(default_factory=list, description="Saldo não agendado com período terminando em até 90 dias.")
    feriados: list[FeriadoLeitura] = Field(default_factory=list, description="Feriados e pontos facultativos da janela exibida.")


class ParametrosLeitura(BaseModel):
    minimo_dias_ferias: int
    minimo_dias_lp: int
    inicio_vedado_ferias: list[int] = Field(..., description="Dias da semana vedados para o início (0 = segunda … 6 = domingo).")
    inicio_vedado_lp: list[int]
    antecedencia_minima_dias: int
    prazo_cancelamento_dias: int = Field(..., description="Cancelar/alterar até N dias antes do início.")
    permite_emenda: bool = Field(..., description="Permite emendar férias e licença-prêmio em sequência.")
    limite_alerta_setor: int = Field(..., description="Alerta com pelo menos N pessoas do mesmo setor afastadas ao mesmo tempo.")
    dias_ferias_por_periodo: int = Field(..., description="Dias de férias creditados no início de cada período aquisitivo.")
    folga_aviso_ferias_dias: int = Field(..., description="Folga do aviso de expiração: 1º aviso = saldo + antecedência mínima + folga antes do fim.")
    aviso_ferias_ativo: bool
    inicio_vedado_feriado: bool = Field(False, description="Períodos não podem começar em feriado ou ponto facultativo cadastrado.")
    atualizado_por_nome: str | None = None
    atualizado_em: datetime | None = None


class GravacaoParametros(BaseModel):
    minimo_dias_ferias: int = Field(..., ge=1, le=90)
    minimo_dias_lp: int = Field(..., ge=1, le=180)
    inicio_vedado_ferias: list[int] = Field(default_factory=list, max_length=7)
    inicio_vedado_lp: list[int] = Field(default_factory=list, max_length=7)
    antecedencia_minima_dias: int = Field(..., ge=0, le=365)
    prazo_cancelamento_dias: int = Field(..., ge=0, le=365)
    permite_emenda: bool
    limite_alerta_setor: int = Field(..., ge=0, le=500, description="0 desliga o alerta.")
    dias_ferias_por_periodo: int = Field(30, ge=1, le=60)
    folga_aviso_ferias_dias: int = Field(15, ge=0, le=180)
    aviso_ferias_ativo: bool = True
    inicio_vedado_feriado: bool = False

    @field_validator("inicio_vedado_ferias", "inicio_vedado_lp")
    @classmethod
    def _dias_da_semana(cls, valor: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in valor):
            raise ValueError("use 0 (segunda) a 6 (domingo)")
        return sorted(set(valor))


MeusAfastamentos.model_rebuild()
