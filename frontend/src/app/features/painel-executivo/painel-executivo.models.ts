// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos dos slides do Painel Executivo (contratos, RH e tarefas) e as funções de apoio.

export type IdSlide = 'contratos' | 'rh' | 'tarefas';

export const ROTULOS_SLIDE: Record<IdSlide, string> = { contratos: 'Contratos', rh: 'RH', tarefas: 'Tarefas' };
export const ORDEM_SLIDES: IdSlide[] = ['contratos', 'rh', 'tarefas'];

export const MESES_CURTOS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

export interface NumerosCarteira {
  contratos_ativos: number;
  contratos_a_vencer: number;
  contratos_encerrados: number;
  valor_global_ativos: string;
  base_mensal_ativos: string;
}

export interface MesExecucao {
  competencia: string;
  previsto: string;
  medido: string;
  pago: string;
}

export interface ExecucaoOrcamentaria {
  exercicio: number;
  meses: MesExecucao[];
  total_previsto: string;
  total_medido: string;
  total_pago: string;
  empenhado: string;
  consumido: string;
  saldo_empenho: string;
}

export interface RiscoResumo {
  contrato_numero: string;
  contrato_apelido: string;
  empresa: string;
  gravidade: 'alta' | 'media';
  riscos: number;
  principal: string;
  rota: string;
}

export interface SlideContratos {
  gerado_em: string;
  exercicio: number;
  numeros: NumerosCarteira;
  execucao: ExecucaoOrcamentaria;
  acumulado: MesExecucao[];
  vencimentos: { ate_dias: number; contratos: number }[];
  alertas_altos: number;
  alertas_medios: number;
  maiores_riscos: RiscoResumo[];
}

export interface SlideRh {
  gerado_em: string;
  ano: number;
  afastados_hoje: { nome: string; setor: string; tipo: 'ferias' | 'licenca_premio'; fim: string }[];
  por_mes: { mes: number; ferias: number; licenca_premio: number }[];
  por_setor: { setor: string; dias: number; pessoas: number }[];
  ferias_a_vencer: { nome: string; setor: string; disponivel: number; periodo_fim: string }[];
  alertas_setor: { setor: string; inicio: string; fim: string; pessoas: number }[];
}

export interface SlideTarefas {
  gerado_em: string;
  abertas: number;
  atrasadas: number;
  vencem_hoje: number;
  criticas: number;
  em_validacao: number;
  concluidas_30_dias: number;
  equipes: { equipe: string; abertas: number; atrasadas: number; criticas: number; carga: number; faixa: string }[];
  semanas: { inicio: string; criadas: number; concluidas: number }[];
}

/** Valor monetário vindo da API (texto com 2 casas) para número; milhares de reais para os gráficos. */
export function emMil(valor: string): number {
  return Number(valor) / 1000;
}

/** "AAAA-MM-DD" para "dd/mm" ou "dd/mm/aaaa", sem passar por fuso horário. */
export function dataCurta(iso: string, comAno = false): string {
  const [a, m, d] = iso.split('-');
  return comAno ? `${d}/${m}/${a}` : `${d}/${m}`;
}

/** Valor em reais por extenso curto para os cartões: R$ 12,3 mi. */
export function moedaCurta(valor: string): string {
  const n = Number(valor);
  const f = (x: number) => x.toLocaleString('pt-BR', { maximumFractionDigits: 1 });
  if (Math.abs(n) >= 1_000_000) return `R$ ${f(n / 1_000_000)} mi`;
  if (Math.abs(n) >= 1_000) return `R$ ${f(n / 1_000)} mil`;
  return `R$ ${f(n)}`;
}
