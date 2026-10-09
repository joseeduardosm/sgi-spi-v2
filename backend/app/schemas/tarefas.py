# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de entrada e saída do Módulo Tarefas.
"""Formatos das rotas `/api/tarefas`."""

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.sla import SlaItem

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
    cor: str = Field(..., description="Hexadecimal da borda da cor (compatibilidade); use `cor_indice`.")
    cor_indice: int = Field(1, ge=0, le=11, description="Cor da paleta de 12 cores (0 = cinza neutro).")
    equipe_id: uuid.UUID | None = None
    usos: int = Field(0, description="Quantas das últimas 1000 tarefas da equipe usam o marcador (só na listagem da equipe).")


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
    dias_em_aberto: int | None = Field(None, description="Dias corridos desde a criação, enquanto a tarefa não está concluída (`null` se concluída).")
    equipe: EquipeResumo | None
    responsavel: Pessoa | None
    responsaveis: list[Pessoa] = Field(..., description="Todos os responsáveis (o principal primeiro, depois os demais por nome), para os avatares do cartão.")
    marcadores: list[MarcadorLeitura]
    checklist_feitos: int
    checklist_total: int
    comentarios: int = Field(..., description="Comentários na linha do tempo (sem os removidos).")
    anexos: int = Field(..., description="Arquivos anexados aos comentários (sem os removidos).")
    carga: float = Field(..., description="Pontos de carga (0 se em validação ou concluída).")
    ordem: int
    criado_em: datetime
    iniciada_em: datetime | None = Field(None, description="Primeira vez em andamento (início da barra no Gantt).")
    concluida_em: datetime | None = None
    atualizado_em: datetime
    tarefa_pai_numero: int | None = Field(None, description="Número da tarefa mãe (quando esta é uma subtarefa).")
    subtarefas_total: int = Field(0, description="Quantas subtarefas a tarefa tem.")
    subtarefas_concluidas: int = 0
    bloqueada: bool = Field(False, description="Há tarefa bloqueadora ainda não concluída (a tarefa não pode iniciar).")
    estagio_id: uuid.UUID | None = Field(None, description="Estágio (coluna) atual na equipe; vazio em tarefa pessoal.")
    marco_id: uuid.UUID | None = Field(None, description="Marco (milestone) da equipe a que a tarefa pertence.")
    origem_tipo: str | None = Field(None, description="Módulo de origem da tarefa (`contrato_competencia` = etapa de uma competência de contrato).")
    sla: SlaItem | None = Field(None, description="SLA de prazos (resposta e resolução em dias úteis, pela prioridade); vazio nas tarefas controladas por outro módulo.")
    controlada_externamente: bool = Field(False, description="O módulo de origem move e conclui a tarefa: o usuário só comenta, anexa e segue (a liderança ajusta responsáveis e prazo).")


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
    tipo: Literal["minhas", "equipe", "pessoa", "subtarefas"]
    titulo: str
    equipe_id: uuid.UUID | None = None
    tarefa_numero: int | None = Field(None, description="`subtarefas`: número da tarefa-mãe cujo quadro de subtarefas está aberto.")
    tarefa_titulo: str | None = Field(None, description="`subtarefas`: título da tarefa-mãe.")
    login: str | None = None
    pessoa_id: int | None = Field(None, description="Id da pessoa do contexto (`minhas` = o próprio usuário; `pessoa` = a pessoa consultada), para o Desempenho individual.")
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


class RecorrenciaResumo(BaseModel):
    """Série a que a tarefa pertence (no detalhe da tarefa)."""
    id: uuid.UUID
    resumo: str
    ativa: bool
    proxima_data: date | None = None
    ocorrencia_em: date | None = Field(None, description="Data do prazo desta ocorrência dentro da série.")


class TarefaLigada(BaseModel):
    """Tarefa relacionada (subtarefa, mãe, bloqueadora ou bloqueada) no detalhe."""
    numero: int
    titulo: str
    status: StatusTarefa
    prazo: datetime
    responsavel: Pessoa | None = None


class NovaSubtarefa(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    descricao: str = Field("", max_length=20000)
    prazo: datetime | None = Field(None, description="Padrão: o prazo da tarefa mãe; não pode passar dele.")
    prioridade: PrioridadeTarefa | None = Field(None, description="Padrão: a da mãe.")
    responsaveis_ids: list[int] = Field(default_factory=list, max_length=50, description="Padrão: os responsáveis da mãe.")

    _t = field_validator("titulo")(lambda cls, v: _aparar(v))


class Dependencias(BaseModel):
    numeros: list[int] = Field(default_factory=list, max_length=30, description="Números das tarefas que bloqueiam esta (substitui a lista atual).")


class TarefaDetalhe(TarefaResumo):
    recorrencia: RecorrenciaResumo | None = None
    tarefa_pai: TarefaLigada | None = None
    subtarefas: list[TarefaLigada] = Field(default_factory=list)
    bloqueada_por: list[TarefaLigada] = Field(default_factory=list, description="Tarefas que bloqueiam esta (inclui as já concluídas).")
    bloqueia: list[TarefaLigada] = Field(default_factory=list, description="Tarefas que esta bloqueia.")
    seguindo: bool = Field(False, description="O usuário segue a tarefa (recebe os avisos informativos).")
    seguidores: list[Pessoa] = Field(default_factory=list)
    pode_criar_subtarefa: bool = Field(False, description="O usuário pode criar subtarefas (edita a tarefa, que não é subtarefa nem está concluída).")
    origem_link: str | None = Field(None, description="Rota do portal da origem (ex.: `/contratos/<id>/execucao/2026-09`), para o link \"Tratar no módulo Contratos\".")
    origem_rotulo: str | None = Field(None, description="Texto do link da origem (ex.: `Contrato 030/2025 · 09/2026`).")
    descricao: str
    usuario_lidera: bool = Field(False, description="O usuário lidera a equipe da tarefa (ou uma acima): pode trocar cor, renomear e excluir marcadores.")
    criado_por: Pessoa | None
    checklist: list[ItemChecklist]
    etapas: list[Etapa]
    segundos_em_andamento: int
    versao: int
    acoes: list[str] = Field(..., description="Ações permitidas ao usuário agora (a tela mostra só estas).")


class RegraRecorrenciaEntrada(BaseModel):
    """Regra de repetição de uma tarefa recorrente (pelo calendário)."""
    frequencia: Literal["diaria", "semanal", "mensal", "anual"]
    intervalo: int = Field(1, ge=1, le=365, description="A cada N dias, semanas, meses ou anos.")
    dias_semana: list[int] = Field(default_factory=list, max_length=7, description="Semanal: dias da semana (0 = segunda … 6 = domingo).")
    somente_dias_uteis: bool = Field(False, description="Data em fim de semana ou feriado vai para o próximo dia útil.")
    antecedencia_dias: int = Field(0, ge=0, le=60, description="A ocorrência é criada N dias antes do prazo (às 07:00).")
    fim: date | None = Field(None, description="Última data possível de prazo.")
    max_ocorrencias: int | None = Field(None, ge=1, le=366, description="Total de ocorrências (a tarefa criada conta como a primeira).")

    @field_validator("dias_semana")
    @classmethod
    def _dias(cls, v: list[int]) -> list[int]:
        if any(d not in range(7) for d in v):
            raise ValueError("os dias da semana vão de 0 (segunda) a 6 (domingo)")
        return sorted(set(v))


class NovaTarefa(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    descricao: str = Field("", max_length=20000)
    prazo: datetime
    prioridade: PrioridadeTarefa = "normal"
    equipe_id: uuid.UUID | None = None
    responsaveis_ids: list[int] = Field(default_factory=list, max_length=50, description="Um ou mais responsáveis, todos com os mesmos poderes; o primeiro é o principal. Vazio: quem cadastra.")
    marcadores_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)
    recorrencia: RegraRecorrenciaEntrada | None = Field(None, description="Cria também a série recorrente: esta tarefa é a primeira ocorrência (o prazo dela define a data inicial e o horário).")

    _t = field_validator("titulo")(lambda cls, v: _aparar(v))


class EdicaoTarefa(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    descricao: str = Field("", max_length=20000)
    prioridade: PrioridadeTarefa
    responsaveis_ids: list[int] = Field(..., min_length=1, max_length=50, description="Todos os responsáveis da tarefa (ao menos um). O principal continua o mesmo se ele estiver na lista; senão, passa a ser o primeiro.")
    marcadores_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)
    versao: int | None = Field(None, description="Versão lida (conflito 409 se outra pessoa alterou antes).")

    _t = field_validator("titulo")(lambda cls, v: _aparar(v))


class MudancaPrazo(BaseModel):
    prazo: datetime
    justificativa: str = Field(..., min_length=1, max_length=2000)
    versao: int | None = None


class Movimento(BaseModel):
    acao: AcaoPipeline
    estagio_id: uuid.UUID | None = Field(None, description="Estágio (coluna) de destino, da categoria da nova situação; vazio = o primeiro estágio dela.")
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
    nome: str = Field(..., min_length=1, max_length=120)
    cor_indice: int | None = Field(None, ge=0, le=11, description="Cor da paleta; vazio na criação sorteia uma (de 1 a 11) e na alteração mantém a atual.")
    cor: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$", description="Hexadecimal (legado): vira a cor da paleta mais próxima; `cor_indice` tem prioridade.")

    _n = field_validator("nome")(lambda cls, v: _aparar(v))


class ContagemEquipe(BaseModel):
    """Tarefas da pessoa numa equipe, por situação (visão da liderança)."""
    a_fazer: int
    em_andamento: int
    em_validacao: int
    concluidas: int
    atrasadas: int


class PessoaCarga(BaseModel):
    """Pessoa com a carga atual (seletor de responsável e visão da liderança). Contagens de todas as tarefas da pessoa."""
    id: int
    nome: str
    login: str
    cargo: str
    carga: float
    faixa: str
    a_fazer: int
    em_andamento: int
    atrasadas: int
    na_equipe: ContagemEquipe | None = Field(None, description="Só com `equipe_id`: contagens das tarefas desta equipe.")


# --- Agenda da pessoa (painel ao atribuir) --------------------------------------------------------

class ItemAgenda(BaseModel):
    """Tarefa em que a pessoa está envolvida, para a lista e a linha do tempo (Gantt) ao atribuir."""
    numero: int
    titulo: str
    status: StatusTarefa
    prioridade: PrioridadeTarefa
    inicio: datetime = Field(..., description="Início da barra: quando entrou em andamento pela 1ª vez ou, se ainda não, a criação.")
    prazo: datetime
    concluida_em: datetime | None
    atrasada: bool
    equipe: EquipeResumo | None
    abrivel: bool = Field(..., description="Quem consulta pode abrir a tarefa (senão, a tela mostra o item sem link).")


class AgendaPessoa(BaseModel):
    """Carga e tarefas de uma pessoa: as abertas (todas) e as concluídas no período."""
    pessoa: PessoaCarga
    de: datetime
    ate: datetime
    itens: list[ItemAgenda]


class PreviaRecorrencia(BaseModel):
    prazo: datetime
    regra: RegraRecorrenciaEntrada


class RespostaPreviaRecorrencia(BaseModel):
    resumo: str
    proximas: list[date] = Field(..., description="As próximas datas de prazo depois da primeira.")


class RecorrenciaLeitura(BaseModel):
    id: uuid.UUID
    equipe: EquipeResumo | None
    titulo: str
    descricao: str
    prioridade: PrioridadeTarefa
    checklist: list[str]
    responsaveis: list[Pessoa]
    marcadores: list[MarcadorLeitura]
    regra: RegraRecorrenciaEntrada
    resumo: str
    inicio: date
    hora_prazo: time
    ativa: bool
    proxima_data: date | None = Field(None, description="Prazo da próxima ocorrência; vazio quando a série terminou.")
    proximas: list[date] = Field(default_factory=list, description="Próximas datas de prazo (até 3).")
    geradas: int
    ultimo_erro: str = Field("", description="Por que a série foi pausada pelo sistema (vazio se não houve erro).")
    criado_por: Pessoa | None
    pode_gerir: bool


class GravacaoRecorrencia(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    descricao: str = Field("", max_length=20000)
    prioridade: PrioridadeTarefa = "normal"
    checklist: list[str] = Field(default_factory=list, max_length=50)
    responsaveis_ids: list[int] = Field(..., min_length=1, max_length=50)
    marcadores_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)
    regra: RegraRecorrenciaEntrada
    hora_prazo: time | None = Field(None, description="Horário do prazo das próximas ocorrências (padrão: o atual).")

    _t = field_validator("titulo")(lambda cls, v: _aparar(v))


class ResumoDesempenho(BaseModel):
    abertas_agora: int
    concluidas_no_periodo: int
    criadas_no_periodo: int
    vazao_media_semanal: float = Field(..., description="Concluídas por semana, em média, no período.")
    ciclo_mediano_dias: float | None = Field(None, description="Mediana do ciclo (primeira vez em andamento → conclusão), em dias.")
    lead_mediano_dias: float | None = Field(None, description="Mediana do lead time (criação → conclusão), em dias.")


class ResumoSlaDesempenho(BaseModel):
    """Cumprimento do SLA no período (tarefas controladas por outro módulo ficam de fora)."""
    resolucoes_no_prazo: int = Field(..., description="Concluídas no período dentro do prazo de resolução.")
    resolucoes_fora: int = Field(..., description="Concluídas no período depois do prazo de resolução.")
    percentual_resolucao: float | None = Field(None, description="% de resoluções no prazo (vazio sem conclusões no período).")
    respostas_no_prazo: int
    respostas_fora: int
    percentual_resposta: float | None = None
    abertas_estouradas: int = Field(..., description="Abertas hoje com o prazo de resolução vencido.")
    abertas_em_risco: int = Field(..., description="Abertas hoje com 80% ou mais do prazo de resolução consumido.")


class SerieBurndown(BaseModel):
    dias: list[date]
    real: list[int | None] = Field(..., description="Tarefas abertas ao fim de cada dia; vazio nos dias futuros.")
    ideal: list[float] = Field(..., description="Linha ideal: do total do início do período até zero no último dia.")
    escopo: list[int] = Field(..., description="Total de tarefas no escopo até cada dia (mostra o que entrou no meio do período).")
    inicial: int = Field(..., description="Tarefas abertas no começo do período.")


class SemanaVazao(BaseModel):
    semana_inicio: date = Field(..., description="Segunda-feira da semana.")
    criadas: int
    concluidas: int
    media_movel: float = Field(..., description="Média das concluídas nas últimas 4 semanas (incluindo esta).")


class SemanaCiclo(BaseModel):
    semana_inicio: date
    concluidas: int
    ciclo_mediana: float | None = None
    ciclo_p85: float | None = None
    lead_mediana: float | None = None
    lead_p85: float | None = None


class SerieFluxo(BaseModel):
    dias: list[date]
    a_fazer: list[int]
    em_andamento: list[int]
    em_validacao: list[int]
    concluida: list[int]


class PessoaDesempenho(BaseModel):
    usuario_id: int
    nome: str
    concluidas: int
    lead_medio_dias: float | None = None
    sla_percentual: float | None = Field(None, description="% das tarefas concluídas no período (com SLA) resolvidas dentro do prazo de resolução.")


class DesempenhoEquipe(BaseModel):
    """Desempenho de uma equipe (`escopo` = equipe) ou de uma pessoa (`escopo` = pessoa; `equipe_id` vazio e `equipe_nome` = nome da pessoa)."""
    escopo: Literal["equipe", "pessoa"] = "equipe"
    equipe_id: uuid.UUID | None = None
    equipe_nome: str
    de: date
    ate: date
    tarefas_no_periodo: int = Field(..., description="Tarefas da equipe e das sub-equipes consideradas.")
    resumo: ResumoDesempenho
    burndown: SerieBurndown
    vazao: list[SemanaVazao]
    ciclo: list[SemanaCiclo]
    fluxo: SerieFluxo
    pessoas: list[PessoaDesempenho]
    sla: ResumoSlaDesempenho | None = Field(None, description="Cumprimento do SLA de tarefas no período.")
    marcos: list["MarcoLeitura"] = Field(default_factory=list, description="Marcos da equipe com progresso e situação.")
    status_atual: "AtualizacaoStatusLeitura | None" = Field(None, description="Última atualização de status publicada pela liderança.")


CategoriaEstagio = Literal["a_fazer", "em_andamento", "em_validacao", "concluida"]


class EstagioLeitura(BaseModel):
    id: uuid.UUID
    nome: str
    categoria: CategoriaEstagio
    posicao: int
    cor_indice: int = Field(..., ge=0, le=11, description="Cor da paleta de 12 cores (a mesma dos marcadores).")


class GravacaoEstagio(BaseModel):
    id: uuid.UUID | None = Field(None, description="Id do estágio existente; vazio cria um novo.")
    nome: str = Field(..., min_length=1, max_length=80)
    categoria: CategoriaEstagio
    cor_indice: int = Field(0, ge=0, le=11)

    _n = field_validator("nome")(lambda cls, v: _aparar(v))


class GravacaoEstagios(BaseModel):
    estagios: list[GravacaoEstagio] = Field(..., min_length=4, max_length=20, description="Lista completa, na ordem das colunas.")


class MudancaEstagio(BaseModel):
    estagio_id: uuid.UUID
    versao: int | None = None


TipoAtividade = Literal["fazer", "ligar", "email", "reuniao", "revisar", "enviar_documento"]


class GravacaoAtividade(BaseModel):
    resumo: str = Field(..., min_length=1, max_length=200)
    tipo: TipoAtividade = "fazer"
    nota: str = Field("", max_length=4000)
    prazo: date | None = Field(None, description="Data da atividade; padrão: hoje.")
    responsavel_id: int | None = Field(None, description="Quem faz a atividade; padrão: quem agenda. Numa equipe, precisa ser da equipe.")

    _r = field_validator("resumo")(lambda cls, v: _aparar(v))


class ConclusaoAtividade(BaseModel):
    feedback: str = Field("", max_length=4000, description="O que foi feito ou combinado (vai para a linha do tempo).")


class AtividadeLeitura(BaseModel):
    id: uuid.UUID
    tarefa_numero: int
    tarefa_titulo: str
    tipo: TipoAtividade
    resumo: str
    nota: str
    prazo: date
    situacao: Literal["atrasada", "hoje", "futura", "concluida"]
    responsavel: Pessoa | None
    criada_por: Pessoa | None
    concluida_em: datetime | None = None
    concluida_por: Pessoa | None = None
    feedback: str = ""
    pode_mexer: bool = False


SituacaoMarco = Literal["no_prazo", "em_risco", "atrasado", "atingido"]
SituacaoStatusEquipe = Literal["no_prazo", "em_risco", "atrasado", "em_espera", "concluido"]


class MarcoLeitura(BaseModel):
    id: uuid.UUID
    nome: str
    descricao: str
    data_alvo: date
    atingido_em: datetime | None
    situacao: SituacaoMarco = Field(..., description="`atingido`; `atrasado` (data-alvo passou); `em_risco` (tarefa atrasada ou com prazo depois da data-alvo); `no_prazo`.")
    total: int = Field(..., description="Tarefas ligadas ao marco.")
    concluidas: int
    atrasadas: int


class GravacaoMarco(BaseModel):
    nome: str = Field(..., min_length=1, max_length=120)
    descricao: str = Field("", max_length=4000)
    data_alvo: date

    _n = field_validator("nome")(lambda cls, v: _aparar(v))


class MarcoDaTarefa(BaseModel):
    marco_id: uuid.UUID | None = Field(None, description="Marco da mesma equipe; vazio tira a tarefa do marco.")


class AtualizacaoStatusLeitura(BaseModel):
    id: uuid.UUID
    situacao: SituacaoStatusEquipe
    texto: str
    autor_nome: str
    criado_em: datetime


class GravacaoStatusEquipe(BaseModel):
    situacao: SituacaoStatusEquipe
    texto: str = Field("", max_length=4000)


DesempenhoEquipe.model_rebuild()


class ResumoSincronizacaoContratos(BaseModel):
    """Resultado da sincronização das tarefas das competências de contratos."""
    ensaio: bool = Field(..., description="Verdadeiro: nada foi gravado (só mostra o que seria feito).")
    competencias: int = Field(..., description="Competências examinadas (regulares, liberadas e dentro do corte).")
    criadas: int = Field(..., description="Tarefas criadas.")
    atualizadas: int = Field(..., description="Tarefas levadas a outro estado, prazo ou título.")
    removidas: int = Field(..., description="Tarefas a fazer que não existem mais na competência (ex.: notas removidas ao zerar).")
    erros: list[str] = Field(default_factory=list, description="Competências que falharam (as demais seguem).")
