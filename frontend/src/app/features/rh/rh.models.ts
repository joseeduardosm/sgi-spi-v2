// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados do Módulo RH (cadastro validado pela CGP, férias e licença-prêmio).

export type TipoAfastamento = 'ferias' | 'licenca_premio';
export type StatusAfastamento = 'pendente' | 'aprovado' | 'recusado' | 'cancelado' | 'gozado';

export interface PapeisRh {
  cgp: boolean;
  autorizador: boolean;
}

export interface AlteracaoCadastral {
  id: string;
  campo: string;
  rotulo: string;
  valor_anterior: string | null;
  valor_anterior_rotulo: string;
  valor_proposto: string | null;
  valor_proposto_rotulo: string;
  status: 'pendente' | 'validada' | 'recusada' | 'substituida';
  solicitada_em: string;
  solicitada_por_nome: string;
  analisada_por_nome: string | null;
  analisada_em: string | null;
  justificativa: string | null;
  valor_corrigido: string | null;
  valor_corrigido_rotulo: string | null;
}

export interface UsuarioPendente {
  usuario_id: number;
  nome: string;
  login: string;
  departamento: string;
  alteracoes: AlteracaoCadastral[];
}

export interface PeriodoAquisitivo {
  /** Ano em que cai a maior parte da janela de gozo (ex.: 31/12/2026 a 30/12/2027 = 2027). */
  exercicio: number;
  inicio: string;
  fim: string;
  dias_creditados: number;
  usado: number;
  disponivel: number;
  dias_expirados: number | null;
  origem: 'automatico' | 'ajuste_cgp';
  vigente: boolean;
}

export interface DadosFuncionais {
  autorizador_id: number | null;
  autorizador_nome: string | null;
  autorizador_sugerido_id: number | null;
  substituto_id: number | null;
  substituto_nome: string | null;
  sem_superior: boolean;
  /** Início do período aquisitivo de férias, "DD/MM". */
  inicio_periodo_aquisitivo: string | null;
  periodos: PeriodoAquisitivo[];
  /** Exercício (ano civil) do saldo de licença-prêmio. */
  exercicio: number | null;
  saldo_lp_dias: number;
  /** Jornada, horários (`HH:MM`) e documentos: exclusivos da CGP. */
  jornada_semanal_horas: number | null;
  regime_plantao: boolean;
  horario_trabalho_inicio: string | null;
  horario_trabalho_fim: string | null;
  horario_estudante: boolean;
  intervalo_inicio: string | null;
  intervalo_fim: string | null;
  rg_cin: string | null;
  rs_pv: string | null;
  atualizado_por_nome: string | null;
  atualizado_em: string | null;
}

export interface CadastroRh {
  usuario_id: number;
  nome: string;
  login: string;
  perfil: Record<string, string | null>;
  pendentes: AlteracaoCadastral[];
  historico: AlteracaoCadastral[];
  funcionais: DadosFuncionais;
}

export interface EventoAfastamento {
  de: string | null;
  para: string;
  autor_nome: string;
  justificativa: string | null;
  ocorrido_em: string;
}

export interface Afastamento {
  id: string;
  usuario_id: number;
  nome: string;
  setor: string;
  tipo: TipoAfastamento;
  inicio: string;
  fim: string;
  dias: number;
  exercicio: number;
  status: StatusAfastamento;
  solicitado_em: string;
  decidido_por_nome: string | null;
  decidido_em: string | null;
  justificativa: string | null;
  substitui_id: string | null;
  /** Etapa 1: aguarda o ciente e de acordo do superior imediato (o aprovador ainda não recebeu o pedido). */
  aguarda_ciencia: boolean;
  ciencia_por_nome: string | null;
  ciencia_em: string | null;
  pode_dar_ciencia: boolean;
  pode_decidir: boolean;
  pode_alterar: boolean;
  eventos: EventoAfastamento[];
}

export interface Saldo {
  saldo: number;
  usado: number;
  disponivel: number;
}

export interface ParametrosRh {
  minimo_dias_ferias: number;
  minimo_dias_lp: number;
  inicio_vedado_ferias: number[];
  inicio_vedado_lp: number[];
  antecedencia_minima_dias: number;
  prazo_cancelamento_dias: number;
  permite_emenda: boolean;
  limite_alerta_setor: number;
  dias_ferias_por_periodo: number;
  folga_aviso_ferias_dias: number;
  aviso_ferias_ativo: boolean;
  /** Períodos não podem começar em feriado ou ponto facultativo cadastrado. */
  inicio_vedado_feriado: boolean;
  /** Abertura do agendamento das férias do ano seguinte (ano da data + 1); vazio desliga a regra. */
  abertura_agendamento_ferias: string | null;
  /** Só leitura: pessoas no setor da CGP (0 = ninguém recebe os avisos da CGP). */
  membros_cgp?: number | null;
  atualizado_por_nome?: string | null;
  atualizado_em?: string | null;
}

export interface PeriodoAtual {
  exercicio: number;
  inicio: string;
  fim: string;
  dias_creditados: number;
  usado: number;
  disponivel: number;
  expira_em_dias: number;
  data_limite_inicio: string | null;
  data_limite_pedido: string | null;
  alerta_expiracao: boolean;
}

/** Agendamento das férias do ano seguinte: depois da abertura, até `limite_dias` dias, sem exigir saldo. */
export interface AgendamentoAntecipado {
  exercicio: number;
  /** Janela do exercício; nulos quando o servidor ainda não tem o início do período informado. */
  inicio: string | null;
  fim: string | null;
  abertura: string;
  aberto: boolean;
  limite_dias: number;
  agendados: number;
}

export interface MeusAfastamentos {
  exercicio: number;
  saldos: Record<TipoAfastamento, Saldo>;
  periodo_vigente: PeriodoAtual | null;
  proximo_periodo: { exercicio: number; inicio: string; fim: string; dias_creditados_previstos: number; usado: number } | null;
  agendamento_antecipado: AgendamentoAntecipado | null;
  afastamentos: Afastamento[];
  parametros: ParametrosRh;
  feriados: Feriado[];
}

export interface AlertaSetor {
  setor: string;
  inicio: string;
  fim: string;
  pessoas: number;
}

export interface PainelAfastamentos {
  visao: 'mensal' | 'anual';
  inicio: string;
  fim: string;
  cgp: boolean;
  periodos: Afastamento[];
  alertas: AlertaSetor[];
  pessoas: { id: number; nome: string; setor: string }[];
  setores: { id: number; nome: string; nivel: number }[];
  ferias_a_vencer: { usuario_id: number; nome: string; setor: string; periodo_inicio: string; periodo_fim: string; disponivel: number; data_limite_pedido: string | null }[];
  feriados: Feriado[];
}

export const ROTULOS_TIPO: Record<TipoAfastamento, string> = { ferias: 'Férias', licenca_premio: 'Licença-prêmio' };
export const SIGLAS_TIPO: Record<TipoAfastamento, string> = { ferias: 'F', licenca_premio: 'LP' };
export const ROTULOS_STATUS: Record<StatusAfastamento, string> = {
  pendente: 'Aguardando aprovação', aprovado: 'Aprovado', recusado: 'Recusado', cancelado: 'Cancelado', gozado: 'Gozado',
};
export const DIAS_SEMANA = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];

export type TipoFeriado = 'feriado' | 'ponto_facultativo';
export type AbrangenciaFeriado = 'nacional' | 'estadual' | 'municipal';

/** Feriado ou ponto facultativo (`FeriadoLeitura` da API). */
export interface Feriado {
  id: string;
  data: string;
  descricao: string;
  tipo: TipoFeriado;
  abrangencia: AbrangenciaFeriado;
  atualizado_por_nome?: string | null;
  atualizado_em?: string | null;
}

export const ROTULOS_TIPO_FERIADO: Record<TipoFeriado, string> = { feriado: 'Feriado', ponto_facultativo: 'Ponto facultativo' };
export const ROTULOS_ABRANGENCIA: Record<AbrangenciaFeriado, string> = { nacional: 'Nacional', estadual: 'Estadual', municipal: 'Municipal' };

/** Mês disponível para a folha de ponto (`CompetenciaFolha` da API). */
export interface CompetenciaFolha {
  valor: string;
  rotulo: string;
  atual: boolean;
}

/** Prévia ou resultado da carga de dados funcionais por planilha. */
export interface ResultadoImportacaoRh {
  total: number;
  com_mudanca: number;
  com_erro: number;
  gravado: boolean;
  linhas: { linha: number; login: string; nome: string; mudancas: string[]; erros: string[] }[];
}

/** Afastamento lançado pela CGP em nome do servidor. */
export interface LancamentoAfastamento {
  usuario_id: number;
  tipo: TipoAfastamento;
  inicio: string;
  fim: string;
  situacao: 'aprovado' | 'gozado';
  justificativa: string;
  ignorar_saldo: boolean;
}
