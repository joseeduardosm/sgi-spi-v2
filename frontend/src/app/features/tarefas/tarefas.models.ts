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
export interface Marcador { id: string; nome: string; cor: string; equipe_id: string | null }

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
  participantes: number;
  marcadores: Marcador[];
  checklist_feitos: number;
  checklist_total: number;
  carga: number;
  ordem: number;
  atualizado_em: string;
}

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

export interface Contexto { tipo: 'minhas' | 'equipe' | 'pessoa'; titulo: string; equipe_id: string | null; login: string | null; lider: boolean }
export interface ListaTarefas { contexto: Contexto; indicadores: Indicadores; itens: TarefaResumo[] }

export interface Etapa { status: StatusTarefa; rotulo: string; em: string | null; por: string | null; atual: boolean; alcancada: boolean }

export interface TarefaDetalhe extends TarefaResumo {
  descricao: string;
  criado_por: Pessoa | null;
  criado_em: string;
  pessoas: Pessoa[];
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
