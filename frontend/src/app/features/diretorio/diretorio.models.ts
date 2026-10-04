// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos e as funções de apoio do Diretório (ramais, aniversariantes e mural de parabéns).

export interface ContatoResumo {
  id: number;
  nome: string;
  cargo: string;
  ramal: string;
  foto_url: string | null;
}

export interface Contato extends ContatoResumo {
  setor: string;
  email: string;
  celular: string;
  whatsapp_url: string;
  linkedin: string;
  andar: string;
  predio: string;
  local: string;
  favorito: boolean;
  /** Preenchidos só enquanto a pessoa está de férias (aprovadas); o selo some sozinho no dia seguinte ao fim. */
  ferias_inicio: string | null;
  ferias_fim: string | null;
}

export interface ContatoDetalhe extends Contato {
  chefia: ContatoResumo | null;
  equipe: ContatoResumo[];
}

export interface PaginaContatos {
  itens: Contato[];
  total: number;
  pagina: number;
  tamanho: number;
}

export interface OpcoesFiltro {
  setores: string[];
  andares: string[];
  predios: string[];
}

export interface FiltrosRamais {
  q: string;
  setor: string;
  andar: string;
  predio: string;
  favoritos: boolean;
  em_ferias: boolean;
}

export type PeriodoAniversario = 'dia' | 'semana' | 'mes';

export const ROTULOS_PERIODO: Record<PeriodoAniversario, string> = { dia: 'Hoje', semana: 'Semana', mes: 'Mês' };

export interface Aniversariante {
  id: number;
  nome: string;
  cargo: string;
  setor: string;
  ramal: string;
  email: string;
  foto_url: string | null;
  dia: number;
  mes: number;
  e_hoje: boolean;
  dias_restantes: number;
  total_parabens: number;
  ja_parabenizei: boolean;
  pode_parabenizar: boolean;
}

export interface Parabens {
  id: string;
  autor_id: number;
  autor_nome: string;
  texto: string;
  criado_em: string;
  meu: boolean;
}

export interface Preferencias {
  foto_url: string | null;
  foto_origem: 'upload' | 'ldap' | null;
  ocultar_aniversario: boolean;
}

export const MAXIMO_RECADO = 500;

/** Até duas iniciais do nome, para o avatar sem foto. */
export function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return '?';
  return (partes[0][0] + (partes.length > 1 ? partes[partes.length - 1][0] : '')).toUpperCase();
}

/** "dd/mm" com dois dígitos. */
export function diaMes(dia: number, mes: number): string {
  return `${String(dia).padStart(2, '0')}/${String(mes).padStart(2, '0')}`;
}

/** Legenda da data de um aniversariante: "Hoje", "Amanhã", "Em 3 dias", "Há 2 dias". */
export function quando(diasRestantes: number): string {
  if (diasRestantes === 0) return 'Hoje';
  if (diasRestantes === 1) return 'Amanhã';
  if (diasRestantes === -1) return 'Ontem';
  return diasRestantes > 0 ? `Em ${diasRestantes} dias` : `Há ${-diasRestantes} dias`;
}

/** "AAAA-MM-DD" para "dd/mm/aaaa" sem passar por fuso horário. */
export function dataBr(iso: string): string {
  const [a, m, d] = iso.split('-');
  return `${d}/${m}/${a}`;
}

/** Texto do selo de férias, ou vazio se a pessoa não está de férias. */
export function seloFerias(c: Pick<Contato, 'ferias_fim'>): string {
  return c.ferias_fim ? `De férias até ${dataBr(c.ferias_fim).slice(0, 5)}` : '';
}
