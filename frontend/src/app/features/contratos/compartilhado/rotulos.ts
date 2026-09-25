// Criado por José Eduardo Santana Martins
// Este arquivo serve para reunir os textos exibidos para os códigos da API e os conversores de números e documentos.

import { Etapa, Papel, Situacao, SituacaoCompetencia, TipoItem } from './contratos.models';

/** Textos exibidos para os códigos da API do módulo de contratos. */

/** Situação do contrato → texto. */
export const ROTULOS_SITUACAO: Record<Situacao, string> = {
  ativo: 'Ativo',
  a_vencer: 'A vencer',
  encerrado: 'Encerrado',
  suspenso: 'Suspenso',
};

/** Os seis papéis da equipe, na ordem de exibição. */
export const PAPEIS: { papel: Papel; rotulo: string }[] = [
  { papel: 'gestor', rotulo: 'Gestor' },
  { papel: 'gestor_suplente', rotulo: 'Suplente do gestor' },
  { papel: 'fiscal_administrativo', rotulo: 'Fiscal administrativo' },
  { papel: 'fiscal_administrativo_suplente', rotulo: 'Suplente administrativo' },
  { papel: 'fiscal_tecnico', rotulo: 'Fiscal técnico' },
  { papel: 'fiscal_tecnico_suplente', rotulo: 'Suplente técnico' },
];

/** Papel → texto (montado a partir da lista acima). */
export const ROTULOS_PAPEL: Record<Papel, string> = Object.fromEntries(PAPEIS.map((p) => [p.papel, p.rotulo])) as Record<Papel, string>;

/** Tipo de item → texto. */
export const ROTULOS_TIPO_ITEM: Record<TipoItem, string> = { continuo: 'Contínuo', sob_demanda: 'Sob demanda' };

/** Opções de periodicidade das competências, em meses. */
export const PERIODICIDADES = [
  { valor: 1, rotulo: 'Mensal' },
  { valor: 2, rotulo: 'Bimestral' },
  { valor: 3, rotulo: 'Trimestral' },
  { valor: 6, rotulo: 'Semestral' },
  { valor: 12, rotulo: 'Anual' },
];

/** Nomes dos meses (índice 0 = janeiro), usados no mês de reajuste. */
export const MESES = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
];

/** Etapa da competência → texto (a etapa "consolidado" aparece como "Download" na tela). */
export const ROTULOS_ETAPA: Record<Etapa, string> = {
  medicao: 'Medição',
  avaliacao: 'Avaliação',
  nota_fiscal: 'Nota fiscal',
  cadin: 'CADIN',
  checklist: 'Checklist',
  consolidado: 'Download',
  ordem_bancaria: 'Ordem Bancária',
  concluida: 'Concluída',
};

/** Situação da competência → texto. */
export const ROTULOS_SITUACAO_COMPETENCIA: Record<SituacaoCompetencia, string> = {
  pendente: 'Pendente',
  disponivel: 'Disponível',
  em_andamento: 'Em andamento',
  concluida: 'Concluída',
};

/** Rótulos dos campos auditados (ícone "quem alterou, quando, de → para"). */
export const ROTULOS_CAMPO: Record<string, string> = {
  numero: 'Número do contrato',
  empresa_id: 'Empresa contratada',
  apelido: 'Apelido',
  objeto: 'Objeto',
  data_inicio: 'Data inicial',
  data_fim: 'Data final',
  vigencia_inicial_meses: 'Vigência inicial (meses)',
  vigencia_maxima_meses: 'Vigência máxima (meses)',
  periodicidade_meses: 'Periodicidade',
  mes_reajuste: 'Mês de reajuste',
  sei_gestao_numero: 'SEI - Gestão (número)',
  sei_gestao_link: 'SEI - Gestão (link)',
  sei_execucao_numero: 'SEI - Execução (número)',
  sei_execucao_link: 'SEI - Execução (link)',
  situacao_forcada: 'Situação forçada',
  valor_global: 'Valor global',
  // Campos da equipe no histórico aparecem como "equipe.<papel>"
  ...Object.fromEntries(PAPEIS.map((p) => [`equipe.${p.papel}`, p.rotulo])),
};

/** Máscara de CNPJ (00.000.000/0000-00) e CPF (000.000.000-00) para exibição. */
export function formatarCnpj(cnpj: string): string {
  return cnpj?.length === 14 ? cnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5') : cnpj;
}

/** CPF com máscara, se tiver 11 dígitos; senão, devolve como veio. */
export function formatarCpf(cpf: string): string {
  return cpf?.length === 11 ? cpf.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4') : cpf;
}

/** Número decimal digitado no padrão brasileiro ("1.234,5") para o texto da API ("1234.5"). */
export function paraDecimalApi(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '0';
  if (typeof valor === 'number') return String(valor);
  // Com vírgula: tira os pontos de milhar e troca a vírgula decimal por ponto
  const texto = valor.trim();
  return texto.includes(',') ? texto.replace(/\./g, '').replace(',', '.') : texto;
}

/** Texto da API ("1234.5000") para edição no padrão brasileiro ("1234,5"). */
export function paraDecimalTela(valor: string | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '';
  const numero = Number(valor);
  return Number.isFinite(numero) ? String(numero).replace('.', ',') : valor;
}

/** Tipos de pendência do painel (etapas da competência e processos em elaboração). */
export const ROTULOS_PENDENCIA: Record<string, string> = {
  ...ROTULOS_ETAPA,
  ciencia_medicao: 'Ciência na medição',
  ciencia_ateste: 'Ciência no ateste',
  base_execucao: 'Gerar competências',
  prorrogacao: 'Prorrogação',
  reajuste: 'Reajuste',
  alteracao: 'Aditamento/supressão',
  ciencia_alteracao: 'Ciência no aditamento/supressão',
};

/** Tipos de risco dos alertas do painel. */
export const ROTULOS_RISCO: Record<string, string> = {
  a_vencer_sem_prorrogacao: 'Vence sem prorrogação',
  vigencia_maxima: 'Vigência máxima atingida',
  reajuste_pendente: 'Reajuste pendente',
  empenho_insuficiente: 'Empenho insuficiente',
  pagamento_vencido: 'Pagamento vencido',
  pagamento_vencendo: 'Pagamento vencendo',
  competencias_atrasadas: 'Competências atrasadas',
};
