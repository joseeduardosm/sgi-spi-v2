// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos do Módulo Tarefas (espelham os schemas de /api/tarefas).

export type StatusTarefa = 'a_fazer' | 'em_andamento' | 'em_validacao' | 'concluida';
export type PrioridadeTarefa = 'baixa' | 'normal' | 'alta' | 'critica';
export type AcaoPipeline = 'iniciar' | 'pausar' | 'entregar' | 'validar' | 'devolver' | 'concluir' | 'reabrir';

export const STATUS: { valor: StatusTarefa; rotulo: string }[] = [
  { valor: 'a_fazer', rotulo: 'A fazer' },
  { valor: 'em_andamento', rotulo: 'Em andamento' },
  { valor: 'em_validacao', rotulo: 'Em validação' },
  { valor: 'concluida', rotulo: 'Concluída' },
];
export const ROTULOS_STATUS: Record<StatusTarefa, string> = Object.fromEntries(STATUS.map((s) => [s.valor, s.rotulo])) as Record<StatusTarefa, string>;
export const ROTULOS_PRIORIDADE: Record<PrioridadeTarefa, string> = { baixa: 'Baixa', normal: 'Normal', alta: 'Alta', critica: 'Crítica' };

export interface Pessoa { id: number; nome: string; login: string }
export interface EquipeResumo { id: string; nome: string }
/** Marcador: `cor_indice` é a cor da paleta de 12 cores; `usos` só vem na listagem da equipe (mais usados primeiro). */
export interface Marcador { id: string; nome: string; cor: string; cor_indice: number; equipe_id: string | null; usos?: number }

import type { SlaItem } from '../sla/sla.models';

export interface TarefaResumo {
  id: string;
  numero: number;
  titulo: string;
  status: StatusTarefa;
  prioridade: PrioridadeTarefa;
  prazo: string;
  prazo_original: string;
  prorrogacoes: number;
  atrasada: boolean;
  equipe: EquipeResumo | null;
  responsavel: Pessoa | null;
  /** Todos os responsáveis (o principal primeiro): avatares do cartão. */
  responsaveis: Pessoa[];
  marcadores: Marcador[];
  checklist_feitos: number;
  checklist_total: number;
  comentarios: number;
  anexos: number;
  carga: number;
  ordem: number;
  criado_em: string;
  iniciada_em: string | null;
  concluida_em: string | null;
  atualizado_em: string;
  /** Número da tarefa mãe, quando esta é uma subtarefa. */
  tarefa_pai_numero: number | null;
  subtarefas_total: number;
  subtarefas_concluidas: number;
  /** Há tarefa bloqueadora ainda não concluída: a tarefa não pode iniciar. */
  bloqueada: boolean;
  /** Coluna (estágio) atual na equipe; vazio em tarefa pessoal. */
  estagio_id: string | null;
  /** Marco (milestone) da equipe a que a tarefa pertence. */
  marco_id: string | null;
  /** Módulo de origem (`contrato_competencia` = etapa de uma competência de contrato). */
  origem_tipo?: string | null;
  /** O módulo de origem move e conclui a tarefa: o usuário só comenta, anexa e segue. */
  controlada_externamente?: boolean;
  /** SLA de prazos (vazio nas tarefas controladas por outro módulo). */
  sla?: SlaItem | null;
}

/** Coluna do quadro da equipe; a `categoria` é a situação do pipeline que ela representa. */
export interface Estagio { id: string; nome: string; categoria: StatusTarefa; posicao: number; cor_indice: number }

/** Tarefa relacionada (mãe, subtarefa, bloqueadora ou bloqueada). */
export interface TarefaLigada { numero: number; titulo: string; status: StatusTarefa; prazo: string; responsavel: Pessoa | null }

export interface Indicadores {
  operacionais: number;
  atrasadas: number;
  vencem_hoje: number;
  criticas: number;
  em_validacao: number;
  concluidas: number;
  carga: number;
  faixa: string;
}

export interface Contexto { tipo: 'minhas' | 'equipe' | 'pessoa'; titulo: string; equipe_id: string | null; login: string | null; pessoa_id: number | null; lider: boolean }
export interface ListaTarefas { contexto: Contexto; indicadores: Indicadores; itens: TarefaResumo[] }

export interface Etapa { status: StatusTarefa; rotulo: string; em: string | null; por: string | null; atual: boolean; alcancada: boolean }

export interface TarefaDetalhe extends TarefaResumo {
  /** Série a que a tarefa pertence (tarefa recorrente). */
  recorrencia: RecorrenciaResumo | null;
  tarefa_pai: TarefaLigada | null;
  subtarefas: TarefaLigada[];
  bloqueada_por: TarefaLigada[];
  bloqueia: TarefaLigada[];
  pode_criar_subtarefa: boolean;
  /** Rota do portal onde a etapa é tratada (ex.: a competência do contrato) e o texto do link. */
  origem_link?: string | null;
  origem_rotulo?: string | null;
  /** O usuário segue a tarefa; `seguidores` são todos que a seguem. */
  seguindo: boolean;
  seguidores: Pessoa[];
  descricao: string;
  /** O usuário lidera a equipe: troca cor, renomeia e exclui marcadores. */
  usuario_lidera: boolean;
  criado_por: Pessoa | null;
  checklist: { id: string; texto: string; concluido: boolean }[];
  etapas: Etapa[];
  segundos_em_andamento: number;
  versao: number;
  acoes: string[];
}

export interface AnexoEvento { id: string; nome: string; tamanho: number; tipo: string; removido: boolean }
export interface EventoTarefa {
  id: string;
  tipo: string;
  titulo: string;
  texto: string;
  dados: Record<string, unknown>;
  autor: string;
  criado_em: string;
  anexos: AnexoEvento[];
  removido: boolean;
  motivo_remocao: string | null;
}
export interface LinhaDoTempo { total: number; itens: EventoTarefa[]; tem_mais: boolean }

export interface PessoaCarga {
  id: number;
  nome: string;
  login: string;
  cargo: string;
  carga: number;
  faixa: string;
  a_fazer: number;
  em_andamento: number;
  atrasadas: number;
  /** Só na lista de uma equipe: tarefas da pessoa nesta equipe, por situação. */
  na_equipe: { a_fazer: number; em_andamento: number; em_validacao: number; concluidas: number; atrasadas: number } | null;
}

export interface Equipe {
  id: string;
  nome: string;
  equipe_pai_id: string | null;
  equipe_pai_nome: string | null;
  dono: Pessoa | null;
  lideres: Pessoa[];
  membros: Pessoa[];
  indicadores: Indicadores;
  lider: boolean;
  pode_configurar: boolean;
}

/** Tarefa da agenda de uma pessoa (painel que aparece ao atribuir). */
export interface ItemAgenda {
  numero: number;
  titulo: string;
  status: StatusTarefa;
  prioridade: PrioridadeTarefa;
  inicio: string;
  prazo: string;
  concluida_em: string | null;
  atrasada: boolean;
  equipe: EquipeResumo | null;
  /** Quem consulta pode abrir a tarefa. */
  abrivel: boolean;
}

export interface AgendaPessoa { pessoa: PessoaCarga; de: string; ate: string; itens: ItemAgenda[] }

export interface FiltrosTarefas {
  status: StatusTarefa[];
  prioridade: PrioridadeTarefa | '';
  marcador_id: string;
  responsavel_id: number | null;
  busca: string;
}

/** "Atrasada há 3 dias", "Vence hoje às 17:00", "Vence em 5 dias". */
export function prazoRelativo(prazo: string, concluida = false): string {
  const alvo = new Date(prazo).getTime();
  const agora = Date.now();
  const dia = 86_400_000;
  if (concluida) return '';
  const hoje = new Date();
  const dataAlvo = new Date(prazo);
  const mesmoDia = dataAlvo.toDateString() === hoje.toDateString();
  if (alvo < agora) {
    const dias = Math.floor((agora - alvo) / dia);
    if (dias >= 1) return `Atrasada há ${dias} dia${dias > 1 ? 's' : ''}`;
    const horas = Math.max(1, Math.floor((agora - alvo) / 3_600_000));
    return `Atrasada há ${horas} h`;
  }
  if (mesmoDia) return `Vence hoje às ${dataAlvo.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
  const dias = Math.ceil((alvo - agora) / dia);
  return dias === 1 ? 'Vence amanhã' : `Vence em ${dias} dias`;
}

/** "3 h 20 min", "2 d 4 h". */
export function duracao(segundos: number): string {
  const d = Math.floor(segundos / 86400);
  const h = Math.floor((segundos % 86400) / 3600);
  const m = Math.floor((segundos % 3600) / 60);
  if (d) return `${d} d ${h} h`;
  if (h) return `${h} h ${m} min`;
  return `${m} min`;
}

/** Tamanho legível ("1,2 MB"). */
export function tamanhoLegivel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB`;
}


// ---------------------------------------------------------------------------------------------
// Funções puras das visões (quadro, lista, calendário e Gantt). Ficam aqui para serem testadas.
// ---------------------------------------------------------------------------------------------

const DIA_MS = 86_400_000;

/** Movimento entre colunas → ação do pipeline. Sem equipe, "concluir" é a própria entrega; com equipe, a API confere a liderança. */
export function acaoEntre(de: StatusTarefa, para: StatusTarefa, semEquipe: boolean): AcaoPipeline | null {
  const mapa: Record<string, AcaoPipeline> = {
    'a_fazer>em_andamento': 'iniciar',
    'em_andamento>a_fazer': 'pausar',
    'em_andamento>em_validacao': 'entregar',
    'em_validacao>concluida': 'validar',
    'em_validacao>em_andamento': 'devolver',
    'concluida>em_andamento': 'reabrir',
    'a_fazer>concluida': 'concluir',
    'em_andamento>concluida': semEquipe ? 'entregar' : 'concluir',
  };
  return mapa[`${de}>${para}`] ?? null;
}

/** Iniciais do avatar: primeira letra do primeiro e do último nome ("Ana Maria Souza" → "AS"). */
export function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return '?';
  const primeira = partes[0][0];
  const ultima = partes.length > 1 ? partes[partes.length - 1][0] : '';
  return (primeira + ultima).toUpperCase();
}

/** Paleta dos avatares (tons sóbrios que contrastam com texto branco). */
const CORES_AVATAR = ['#2f6fb5', '#2e8b57', '#6b3f99', '#b7591f', '#1f8a99', '#8a3f6b', '#4f6d2f', '#a8322d', '#3f5a99', '#7a5a1f'];

/** Cor fixa por pessoa (o mesmo id tem sempre a mesma cor). */
export function corAvatar(id: number): string {
  return CORES_AVATAR[Math.abs(id) % CORES_AVATAR.length];
}

export type SituacaoPrazo = 'concluida' | 'atrasada' | 'proxima' | 'normal';

/** Cor do chip de prazo: atrasada (vermelho), vence hoje ou amanhã (âmbar), no prazo (cinza), concluída (verde). */
export function situacaoPrazo(t: Pick<TarefaResumo, 'status' | 'prazo'>, agora = new Date()): SituacaoPrazo {
  if (t.status === 'concluida') return 'concluida';
  const prazo = new Date(t.prazo);
  if (prazo.getTime() < agora.getTime()) return 'atrasada';
  const amanha = new Date(agora);
  amanha.setDate(amanha.getDate() + 1);
  amanha.setHours(23, 59, 59, 999);
  return prazo.getTime() <= amanha.getTime() ? 'proxima' : 'normal';
}

/** Prazo padrão da criação rápida: daqui a 7 dias, às 18:00 (horário local). */
export function prazoPadrao(agora = new Date()): Date {
  const d = new Date(agora);
  d.setDate(d.getDate() + 7);
  d.setHours(18, 0, 0, 0);
  return d;
}

/** Raia do quadro: uma pessoa (ou "Sem responsável") e as tarefas em que ela é a responsável. */
export interface Raia { pessoa: Pessoa | null; itens: TarefaResumo[] }

/** Agrupa por responsável, em ordem de nome; "Sem responsável" vai por último. */
export function agruparRaias(itens: TarefaResumo[]): Raia[] {
  const mapa = new Map<number, Raia>();
  const sem: TarefaResumo[] = [];
  for (const t of itens) {
    if (!t.responsavel) { sem.push(t); continue; }
    const raia = mapa.get(t.responsavel.id) ?? { pessoa: t.responsavel, itens: [] };
    raia.itens.push(t);
    mapa.set(t.responsavel.id, raia);
  }
  const raias = [...mapa.values()].sort((a, b) => a.pessoa!.nome.localeCompare(b.pessoa!.nome));
  return sem.length ? [...raias, { pessoa: null, itens: sem }] : raias;
}

/** Chave do dia no horário local ("2026-09-30"). */
export function chaveDia(d: Date): string {
  const z = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

/** Semanas (domingo a sábado) que cobrem o mês `mes` (0 = janeiro) do ano. */
export function semanasDoMes(ano: number, mes: number): Date[][] {
  const primeiro = new Date(ano, mes, 1);
  const inicio = new Date(ano, mes, 1 - primeiro.getDay());
  const semanas: Date[][] = [];
  const cursor = new Date(inicio);
  do {
    const semana: Date[] = [];
    for (let i = 0; i < 7; i++) {
      semana.push(new Date(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    semanas.push(semana);
  } while (cursor.getMonth() === mes);
  return semanas;
}

/** Tarefas agrupadas pelo dia do prazo (chave de `chaveDia`), cada dia em ordem de horário. */
export function porDiaDoPrazo<T extends { prazo: string }>(itens: T[]): Map<string, T[]> {
  const mapa = new Map<string, T[]>();
  for (const t of [...itens].sort((a, b) => a.prazo.localeCompare(b.prazo))) {
    const chave = chaveDia(new Date(t.prazo));
    mapa.set(chave, [...(mapa.get(chave) ?? []), t]);
  }
  return mapa;
}

/** Barra do Gantt em % da janela: início (ou a entrada em andamento) até o prazo, ou até a conclusão. */
export interface BarraGantt { esquerda: number; largura: number; cortadaInicio: boolean; cortadaFim: boolean }

/**
 * Posição da barra de uma tarefa numa janela de `dias` dias a partir de `inicioJanela` (meia-noite local).
 * A barra tem ao menos meio dia de largura, para ficar visível; partes fora da janela são cortadas.
 */
export function barraGantt(item: Pick<ItemAgenda, 'inicio' | 'prazo' | 'concluida_em'>, inicioJanela: Date, dias: number): BarraGantt | null {
  const janelaIni = inicioJanela.getTime();
  const janelaFim = janelaIni + dias * DIA_MS;
  const ini = new Date(item.inicio).getTime();
  let fim = new Date(item.concluida_em ?? item.prazo).getTime();
  if (fim < ini) fim = ini;
  if (fim < janelaIni || ini > janelaFim) return null;
  const a = Math.max(ini, janelaIni);
  const b = Math.max(Math.min(fim, janelaFim), a + DIA_MS / 2);
  const total = janelaFim - janelaIni;
  return {
    esquerda: ((a - janelaIni) / total) * 100,
    largura: (Math.min(b, janelaFim) - a) / total * 100,
    cortadaInicio: ini < janelaIni,
    cortadaFim: fim > janelaFim,
  };
}

// --- Tarefas recorrentes ---------------------------------------------------------------------------

export type FrequenciaRecorrencia = 'diaria' | 'semanal' | 'mensal' | 'anual';

/** Regra de repetição (pelo calendário). `dias_semana`: 0 = segunda … 6 = domingo. */
export interface RegraRecorrencia {
  frequencia: FrequenciaRecorrencia;
  intervalo: number;
  dias_semana: number[];
  somente_dias_uteis: boolean;
  antecedencia_dias: number;
  fim: string | null;
  max_ocorrencias: number | null;
}

export interface RecorrenciaResumo { id: string; resumo: string; ativa: boolean; proxima_data: string | null; ocorrencia_em: string | null }

export interface Recorrencia {
  id: string;
  equipe: EquipeResumo | null;
  titulo: string;
  descricao: string;
  prioridade: PrioridadeTarefa;
  checklist: string[];
  responsaveis: Pessoa[];
  marcadores: Marcador[];
  regra: RegraRecorrencia;
  resumo: string;
  inicio: string;
  hora_prazo: string;
  ativa: boolean;
  proxima_data: string | null;
  proximas: string[];
  geradas: number;
  ultimo_erro: string;
  criado_por: Pessoa | null;
  pode_gerir: boolean;
}

export const DIAS_SEMANA_CURTOS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];

/** Regra padrão ao ligar "Repetir": toda semana, no dia da semana do prazo. */
export function regraPadrao(diaDaSemana: number): RegraRecorrencia {
  return { frequencia: 'semanal', intervalo: 1, dias_semana: [diaDaSemana], somente_dias_uteis: false, antecedencia_dias: 0, fim: null, max_ocorrencias: null };
}

// --- Desempenho da equipe (burndown e vazão) ------------------------------------------------------

/** Cumprimento do SLA no período (Desempenho). */
export interface ResumoSlaDesempenho {
  resolucoes_no_prazo: number;
  resolucoes_fora: number;
  percentual_resolucao: number | null;
  respostas_no_prazo: number;
  respostas_fora: number;
  percentual_resposta: number | null;
  abertas_estouradas: number;
  abertas_em_risco: number;
}

export interface DesempenhoEquipe {
  /** `equipe` (padrão) ou `pessoa`: neste caso `equipe_id` vem vazio e `equipe_nome` traz o nome da pessoa. */
  escopo?: 'equipe' | 'pessoa';
  equipe_id: string | null;
  equipe_nome: string;
  de: string;
  ate: string;
  tarefas_no_periodo: number;
  resumo: { abertas_agora: number; concluidas_no_periodo: number; criadas_no_periodo: number; vazao_media_semanal: number; ciclo_mediano_dias: number | null; lead_mediano_dias: number | null };
  burndown: { dias: string[]; real: (number | null)[]; ideal: number[]; escopo: number[]; inicial: number };
  vazao: { semana_inicio: string; criadas: number; concluidas: number; media_movel: number }[];
  ciclo: { semana_inicio: string; concluidas: number; ciclo_mediana: number | null; ciclo_p85: number | null; lead_mediana: number | null; lead_p85: number | null }[];
  fluxo: { dias: string[]; a_fazer: number[]; em_andamento: number[]; em_validacao: number[]; concluida: number[] };
  pessoas: { usuario_id: number; nome: string; concluidas: number; lead_medio_dias: number | null; sla_percentual?: number | null }[];
  sla?: ResumoSlaDesempenho | null;
  marcos: Marco[];
  status_atual: AtualizacaoStatus | null;
}

// --- Atividades agendadas ---------------------------------------------------------------------------

export type TipoAtividade = 'fazer' | 'ligar' | 'email' | 'reuniao' | 'revisar' | 'enviar_documento';

export const ROTULOS_TIPO_ATIVIDADE: Record<TipoAtividade, string> = {
  fazer: 'A fazer', ligar: 'Ligar', email: 'E-mail', reuniao: 'Reunião', revisar: 'Revisar', enviar_documento: 'Enviar documento',
};
export const ICONES_TIPO_ATIVIDADE: Record<TipoAtividade, string> = { fazer: '✔', ligar: '☎', email: '✉', reuniao: '👥', revisar: '🔍', enviar_documento: '📎' };

export interface Atividade {
  id: string;
  tarefa_numero: number;
  tarefa_titulo: string;
  tipo: TipoAtividade;
  resumo: string;
  nota: string;
  prazo: string;
  situacao: 'atrasada' | 'hoje' | 'futura' | 'concluida';
  responsavel: Pessoa | null;
  criada_por: Pessoa | null;
  concluida_em: string | null;
  concluida_por: Pessoa | null;
  feedback: string;
  pode_mexer: boolean;
}

// --- Marcos e status da equipe ---------------------------------------------------------------------

export type SituacaoMarco = 'no_prazo' | 'em_risco' | 'atrasado' | 'atingido';
export type SituacaoStatusEquipe = 'no_prazo' | 'em_risco' | 'atrasado' | 'em_espera' | 'concluido';

export interface Marco {
  id: string;
  nome: string;
  descricao: string;
  data_alvo: string;
  atingido_em: string | null;
  situacao: SituacaoMarco;
  total: number;
  concluidas: number;
  atrasadas: number;
}

export interface AtualizacaoStatus { id: string; situacao: SituacaoStatusEquipe; texto: string; autor_nome: string; criado_em: string }

export const ROTULOS_SITUACAO_MARCO: Record<SituacaoMarco, string> = { no_prazo: 'No prazo', em_risco: 'Em risco', atrasado: 'Atrasado', atingido: 'Atingido' };
export const ROTULOS_STATUS_EQUIPE: Record<SituacaoStatusEquipe, string> = { no_prazo: 'No prazo', em_risco: 'Em risco', atrasado: 'Atrasado', em_espera: 'Em espera', concluido: 'Concluído' };
