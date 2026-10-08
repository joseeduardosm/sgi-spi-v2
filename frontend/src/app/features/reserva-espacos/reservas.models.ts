// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos e utilitários de formatação da Reserva de Espaços.

export type StatusReserva = 'AGUARDANDO_APROVACAO' | 'DEFERIDA' | 'INDEFERIDA' | 'CANCELADA';
export type Recorrencia = 'nenhuma' | 'diaria' | 'semanal' | 'quinzenal' | 'mensal';
export type EscopoCancelamento = 'ocorrencia' | 'serie' | 'periodo';

export interface Espaco {
  id: number;
  nome: string;
  localizacao: string;
  cor: string;
  capacidade: number | null;
  equipamentos: string;
  descricao: string;
  ativo: boolean;
}

export interface Contexto {
  eh_fiscal: boolean;
  espacos: Espaco[];
}

export interface Reserva {
  id: number;
  espaco_id: number;
  espaco_nome: string;
  espaco_cor: string;
  data: string;
  hora_inicio: string;
  hora_fim: string;
  titulo: string;
  responsavel_id: number | null;
  responsavel_nome: string;
  solicitante_id: number | null;
  solicitante_nome: string;
  observacoes: string;
  participantes: number | null;
  status: StatusReserva;
  fiscal_nome: string;
  justificativa: string;
  serie_id: string | null;
  ocorrencias_serie: number;
  pode_editar: boolean;
  pode_cancelar: boolean;
  pode_analisar: boolean;
  criado_em: string;
}

export interface Evento {
  id: number;
  tipo: string;
  usuario_nome: string;
  detalhes: Record<string, unknown> | null;
  criado_em: string;
}

export interface ReservaDetalhe extends Reserva {
  eventos: Evento[];
  serie: Reserva[];
}

export interface ListaReservas {
  total: number;
  itens: Reserva[];
}

export interface GravacaoReserva {
  espaco_id: number;
  data: string;
  hora_inicio: string;
  hora_fim: string;
  titulo: string;
  observacoes: string;
  participantes: number | null;
  recorrencia: Recorrencia;
  recorrencia_ate: string | null;
  responsavel_id: number | null;
  responsavel_nome: string;
}

export interface ResultadoSolicitacao {
  reservas: Reserva[];
  avisos: string[];
}

export interface UsuarioBusca {
  id: number;
  nome: string;
  login: string;
}

export interface Configuracao {
  hora_abertura: string;
  hora_fechamento: string;
  antecedencia_minima_horas: number;
  duracao_maxima_horas: number;
  fiscais: UsuarioBusca[];
}

export interface Painel {
  ano: number;
  mes: number;
  total: number;
  deferidas: number;
  indeferidas: number;
  aguardando: number;
  canceladas: number;
  espacos_ativos: number;
  media_por_dia: number;
  por_mes: { mes: number; rotulo: string; total: number }[];
  ocupacao: { espaco: string; cor: string; horas: number; reservas: number; ocupacao_percentual: number }[];
  pessoas: { nome: string; total: number }[];
}

export const ROTULOS_STATUS: Record<StatusReserva, string> = {
  AGUARDANDO_APROVACAO: 'Aguardando aprovação',
  DEFERIDA: 'Deferida',
  INDEFERIDA: 'Indeferida',
  CANCELADA: 'Cancelada',
};

export const ROTULOS_EVENTO: Record<string, string> = {
  CRIACAO: 'Solicitação criada',
  EDICAO: 'Reserva alterada',
  CANCELAMENTO: 'Reserva cancelada',
  DEFERIMENTO: 'Reserva deferida',
  INDEFERIMENTO: 'Reserva indeferida',
  LEMBRETE: 'Lembrete enviado',
};

export const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];

/** Data ISO (aaaa-mm-dd) para o formato brasileiro, sem passar por fuso. */
export function dataBr(iso: string): string {
  const [a, m, d] = iso.split('-');
  return `${d}/${m}/${a}`;
}

/** Horário HH:MM:SS da API para HH:MM. */
export function horaCurta(hora: string): string {
  return hora.slice(0, 5);
}

/** Data local como aaaa-mm-dd (o `toISOString` usaria UTC e poderia mudar o dia). */
export function isoLocal(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
