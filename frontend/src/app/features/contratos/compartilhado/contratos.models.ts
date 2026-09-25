/**
 * Tipos do módulo de contratos, espelhando os schemas da API (docs/endpoints/contratos-*.md).
 * Valores decimais chegam como texto ("1234.50") para não perder precisão.
 */

export type Decimal = string;
export type TipoItem = 'continuo' | 'sob_demanda';
export type Situacao = 'ativo' | 'a_vencer' | 'encerrado' | 'suspenso';
export type Papel =
  | 'gestor'
  | 'gestor_suplente'
  | 'fiscal_administrativo'
  | 'fiscal_administrativo_suplente'
  | 'fiscal_tecnico'
  | 'fiscal_tecnico_suplente';
export type Etapa = 'medicao' | 'avaliacao' | 'nota_fiscal' | 'cadin' | 'checklist' | 'consolidado' | 'ordem_bancaria' | 'concluida';
export type SituacaoCompetencia = 'pendente' | 'disponivel' | 'em_andamento' | 'concluida';

export interface Pagina<T> {
  itens: T[];
  total: number;
  pagina: number;
  tamanho_pagina: number;
}

export interface Arquivo {
  anexo_id: string;
  nome: string;
  tamanho: number;
  enviado_em: string;
}

export interface Ciencia {
  usuario_id: number | null;
  nome: string;
  papel: Papel;
  registrada_em: string;
}

// --- Empresas ---------------------------------------------------------------------------------

export interface ContratoDaEmpresa {
  id: string;
  numero: string;
}

export interface ResumoEmpresa {
  id: string;
  cnpj: string;
  razao_social: string;
  nome_fantasia: string;
  endereco: string;
  ativa: boolean;
  prepostos: string[];
  contratos: ContratoDaEmpresa[];
}

export interface Preposto {
  id: string;
  cpf: string;
  nome: string;
  telefone: string;
  email: string;
  cargo: string;
  ativo: boolean;
}

export interface DetalheEmpresa extends Omit<ResumoEmpresa, 'prepostos'> {
  prepostos: Preposto[];
  criado_em: string;
  atualizado_em: string;
}

export interface OpcaoEmpresa {
  id: string;
  cnpj: string;
  razao_social: string;
  nome_fantasia: string;
  ativa: boolean;
}

export interface GravacaoEmpresa {
  cnpj: string;
  razao_social: string;
  nome_fantasia: string;
  endereco: string;
  ativa: boolean;
}

export type GravacaoPreposto = Omit<Preposto, 'id'>;

// --- Contrato ---------------------------------------------------------------------------------

export interface ResumoContrato {
  id: string;
  numero: string;
  apelido: string;
  empresa_razao_social: string;
  objeto: string;
  data_inicio: string;
  data_fim: string;
  situacao: Situacao;
  base_mensal: Decimal;
  valor_global: Decimal;
}

export interface ItemContrato {
  id: string;
  ordem: number;
  descricao: string;
  tipo: TipoItem;
  calcula_pro_rata: boolean;
  codigo_classe: string;
  codigo_natureza_despesa: string;
  codigo_siafisico: string;
  codigo_catmat_catser: string;
  quantidade_mensal: Decimal;
  quantidade_total: Decimal;
  quantidade_original: Decimal;
  quantidade_executada: Decimal;
  quantidade_disponivel: Decimal;
  valor_unitario: Decimal;
  subtotal_mensal: Decimal;
  vigencia_meses: number;
}

export interface MembroEquipe {
  papel: Papel;
  usuario_id: number;
  nome: string;
  login: string;
  desde: string | null;
}

export interface Vigencia {
  sequencia: number;
  inicio: string;
  fim: string;
  meses: number;
}

export interface Marco {
  data: string;
  tipo: 'inicio' | 'prazo_inicial' | 'termo_aditivo' | 'reajuste' | 'aditamento' | 'supressao' | 'vigencia_atual' | 'maximo';
  rotulo: string;
}

export interface DetalheContrato extends ResumoContrato {
  sequencial: number;
  ano: number;
  empresa: OpcaoEmpresa;
  data_fim_prazo_inicial: string;
  data_limite_maxima: string;
  vigencia_inicial_meses: number;
  vigencia_maxima_meses: number;
  periodicidade_meses: number;
  mes_reajuste: number;
  sei_gestao_numero: string;
  sei_gestao_link: string;
  sei_execucao_numero: string;
  sei_execucao_link: string;
  situacao_forcada: Situacao | null;
  vigencias: Vigencia[];
  marcos: Marco[];
  aditamento_acumulado_percentual: Decimal;
  supressao_acumulada_percentual: Decimal;
  itens: ItemContrato[];
  equipe: MembroEquipe[];
  criador_nome: string | null;
  permissoes: { pode_editar: boolean; pode_excluir: boolean };
  versao: number;
  criado_em: string;
  atualizado_em: string;
}

export interface GravacaoItem {
  id: string | null;
  descricao: string;
  tipo: TipoItem;
  calcula_pro_rata: boolean;
  codigo_classe: string;
  codigo_natureza_despesa: string;
  codigo_siafisico: string;
  codigo_catmat_catser: string;
  quantidade_mensal: Decimal;
  quantidade_total: Decimal;
  valor_unitario: Decimal;
}

export type GravacaoEquipe = Partial<Record<Papel, number | null>>;

export interface GravacaoContrato {
  numero: string;
  empresa_id: string;
  apelido: string;
  objeto: string;
  data_inicio: string;
  vigencia_inicial_meses: number;
  vigencia_maxima_meses: number;
  periodicidade_meses: number;
  mes_reajuste: number;
  sei_gestao_numero: string;
  sei_gestao_link: string;
  sei_execucao_numero: string;
  sei_execucao_link: string;
  situacao_forcada: Situacao | null;
  equipe: GravacaoEquipe;
  itens: GravacaoItem[];
  versao: number | null;
}

export interface DocumentoContrato {
  codigo: number;
  numero: string;
  titulo: string;
  anexado: boolean;
  nome_arquivo: string;
  tamanho: number | null;
  enviado_em: string | null;
  enviado_por_nome: string | null;
}

export interface AlteracaoCampo {
  campo: string;
  de: unknown;
  para: unknown;
  autor: string;
  ocorrido_em: string;
}

// --- Orçamento --------------------------------------------------------------------------------

export interface ItemMesPrevisao {
  item_id: string;
  ordem: number;
  descricao: string;
  tipo: TipoItem;
  quantidade: Decimal;
  valor_unitario: Decimal;
  fator: Decimal;
  subtotal: Decimal;
}

export interface MesPrevisao {
  competencia: string;
  sequencia_vigencia: number;
  inicio: string;
  fim: string;
  fator: Decimal;
  base_mensal: Decimal;
  valor: Decimal;
  acumulado: Decimal;
  itens: ItemMesPrevisao[];
}

export interface ItemSobDemandaPrevisao {
  item_id: string;
  ordem: number;
  descricao: string;
  limite: Decimal;
  apontamentos: Record<string, Decimal>;
  saldo: Decimal;
}

export interface VigenciaPrevisao {
  sequencia: number;
  inicio: string;
  fim: string;
  meses: string[];
  possui_sob_demanda: boolean;
  salva: boolean;
  salva_em: string | null;
  salva_por_nome: string | null;
  pode_editar: boolean;
  itens_sob_demanda: ItemSobDemandaPrevisao[];
  total_previsto: Decimal;
}

export interface Previsao {
  total_previsto: Decimal;
  vigencias: VigenciaPrevisao[];
  meses: MesPrevisao[];
}

export interface MovimentoNota {
  id: string;
  data: string;
  tipo: 'pagamento' | 'estorno';
  competencia: string | null;
  competencia_id: string | null;
  competencia_rotulo: string | null;
  debito: Decimal;
  saldo_apos: Decimal;
  justificativa: string;
  autor: string | null;
}

export interface NotaEmpenho {
  id: string;
  numero: string;
  valor_original: Decimal;
  consumido: Decimal;
  saldo: Decimal;
  comprometido: Decimal;
  saldo_livre: Decimal;
  percentual_consumido: Decimal;
  faixa: 'verde' | 'amarelo' | 'vermelho';
  vinculada: boolean;
  movimentos: MovimentoNota[];
  criado_em: string;
}

// --- Execução ---------------------------------------------------------------------------------

export interface DocumentoChecklist {
  id: string;
  ordem: number;
  nome: string;
  observacao: string;
  /** Obrigatório precisa estar anexado para concluir a etapa; opcional, não. */
  obrigatorio: boolean;
}

export interface Checklist {
  id: string;
  versao: number;
  nome: string;
  ativo: boolean;
  itens: DocumentoChecklist[];
  criado_por_nome: string;
  criado_em: string;
  ativado_em: string | null;
}

export interface NotaEscala {
  valor: Decimal;
  legenda: string;
}

export interface FaixaLiberacao {
  minimo: Decimal;
  maximo: Decimal | null;
  percentual: Decimal;
  notas_zero?: number | null;
}

export interface ItemFormulario {
  id?: string | null;
  nome: string;
  descricao: string;
  peso: Decimal;
}

export interface GrupoFormulario {
  id?: string | null;
  nome: string;
  itens: ItemFormulario[];
}

export interface DefinicaoFormulario {
  escala: NotaEscala[];
  faixas: FaixaLiberacao[];
  grupos: GrupoFormulario[];
}

export interface Formulario {
  id: string;
  versao: number;
  nome: string;
  ativo: boolean;
  definicao: DefinicaoFormulario;
  criado_por_nome: string;
  criado_em: string;
  ativado_em: string | null;
}

export interface Modelo {
  id: string;
  tipo: 'checklist' | 'formulario';
  nome: string;
  conteudo: { itens?: { nome: string; observacao: string; obrigatorio?: boolean }[] } & Partial<DefinicaoFormulario>;
  ativo: boolean;
  atualizado_em: string;
}

export interface ResumoCompetencia {
  id: string;
  competencia: string;
  tipo: 'regular' | 'diferenca_reajuste';
  parte: number | null;
  identificador: string;
  rotulo: string;
  sequencia_vigencia: number;
  periodo_inicio: string;
  periodo_fim: string;
  situacao: SituacaoCompetencia;
  etapa_atual: Etapa;
  valor_medicao: Decimal | null;
  possui_avaliacao: boolean;
}

export interface PainelExecucao {
  requisitos: { prontos: boolean; pendencias: string[] };
  geradas: boolean;
  grupos: { sequencia_vigencia: number; inicio: string; fim: string; competencias: ResumoCompetencia[] }[];
}

export interface ItemMedicao {
  id: string;
  ordem: number;
  descricao: string;
  tipo: TipoItem;
  calcula_pro_rata: boolean;
  valor_unitario: Decimal;
  fator_meses: Decimal;
  quantidade_prevista: Decimal;
  quantidade_medida: Decimal;
  subtotal: Decimal;
}

export interface NotaSelecionada {
  id: string;
  numero: string;
  saldo: Decimal;
  saldo_livre: Decimal;
}

export interface NotaFiscal {
  numero: string;
  arquivo: Arquivo | null;
  valor_bruto: Decimal | null;
  retencao_ir: Decimal;
  retencao_inss: Decimal;
  retencao_iss: Decimal;
  retencao_pis: Decimal;
  retencao_cofins: Decimal;
  valor_liquido: Decimal;
}

export interface RespostaAvaliacao {
  item_id: string;
  nota: Decimal;
  justificativa: string;
}

export interface AssinaturaAteste {
  papel: 'gestor' | 'fiscal_administrativo' | 'fiscal_tecnico';
  usuario_id: number;
  nome: string;
  ciencia_em: string | null;
}

export interface Avaliacao {
  definicao: DefinicaoFormulario & { grupos: (GrupoFormulario & { id: string; itens: (ItemFormulario & { id: string })[] })[] };
  respostas_iniciais: RespostaAvaliacao[];
  avaliacao_inicial_em: string | null;
  respostas_gestor: RespostaAvaliacao[];
  complemento_gestor: string;
  avaliacao_gestor_em: string | null;
  nota_final: Decimal | null;
  percentual_liberado: Decimal | null;
  assinaturas: AssinaturaAteste[];
  assinaturas_definidas_em: string | null;
  pdf_gerado: Arquivo | null;
  pdf_assinado: Arquivo | null;
  concluida_em: string | null;
  reconsideracoes: number;
  reconsideracao: Arquivo | null;
}

export interface ConsultaCadin {
  id: string;
  possui_pendencia: boolean;
  pendencia: string;
  texto_notificacao: string;
  certidao: Arquivo;
  email: Arquivo | null;
  criado_por_nome: string;
  criado_em: string;
}

export interface DocumentoMensal {
  id: string;
  ordem: number;
  nome: string;
  observacao: string;
  obrigatorio: boolean;
  arquivo: Arquivo | null;
}

export interface DetalheCompetencia extends ResumoCompetencia {
  contrato_id: string;
  contrato_numero: string;
  etapas: Etapa[];
  pode_editar: boolean;
  integra_equipe: boolean;
  liberada: boolean;
  itens: ItemMedicao[];
  total_previsto: Decimal;
  total_medido: Decimal;
  notas_selecionadas: NotaSelecionada[];
  notas_disponiveis: NotaSelecionada[];
  ciencias: Ciencia[];
  ciencias_minimas: number;
  memorias: { versao: number; criada_em: string; arquivo: Arquivo }[];
  medicao_concluida_em: string | null;
  avaliacao: Avaliacao | null;
  percentual_autorizado: Decimal;
  valor_autorizado: Decimal;
  valor_a_pagar: Decimal;
  avisos: string[];
  reaberturas_permitidas: boolean;
  nota_fiscal: NotaFiscal | null;
  nota_fiscal_adicional: NotaFiscal | null;
  nf_recebida_em: string | null;
  prazo_pagamento_dias: number | null;
  vencimento_pagamento: string | null;
  origem_valor_nf: 'medicao' | 'manual' | null;
  nf_concluida_em: string | null;
  consultas_cadin: ConsultaCadin[];
  documentos: DocumentoMensal[];
  consolidado: Arquivo | null;
  ordem_bancaria: Arquivo | null;
  concluida_em: string | null;
}

// --- Prorrogação, reajuste, aditamento/supressão -----------------------------------------------

export interface PlanoItemProrrogacao {
  item_id: string;
  ordem: number;
  descricao: string;
  quantidade_original: Decimal;
  saldo_remanescente: Decimal;
  limite: Decimal;
  apontamentos: Record<string, Decimal>;
  saldo: Decimal;
}

export type RegraSobDemanda = 'saldo_remanescente' | 'repetir_inicial' | 'manual';

export interface CamposParecer {
  avaliacao_geral: string;
  resumo_qualidade: string;
  historico_ocorrencias: string;
  reclamacoes: string;
  atendimento_chamados: string;
  parecer: string;
}

export interface ProcessoProrrogacao extends CamposParecer {
  id: string | null;
  vigencia_atual_inicio: string;
  vigencia_atual_fim: string;
  meses: number | null;
  nova_vigencia_inicio: string;
  nova_vigencia_fim: string | null;
  meses_disponiveis: number;
  meses_nova_vigencia: string[];
  regra_sob_demanda: RegraSobDemanda;
  itens_sob_demanda: PlanoItemProrrogacao[];
  possui_parecer: boolean;
  ciencias: Ciencia[];
  relatorio: Arquivo | null;
  exige_checklist_ativo: boolean;
  pode_editar: boolean;
  integra_equipe: boolean;
}

export interface Prorrogacao {
  id: string;
  meses: number;
  assinada_em: string;
  numero_termo: string;
  fim_anterior: string;
  data_inicio: string;
  data_fim: string;
  codigo_documento: number | null;
  termo: Arquivo | null;
  relatorio: Arquivo | null;
  pode_desfazer: boolean;
}

export interface ItemReajuste {
  item_id: string;
  ordem: number;
  descricao: string;
  tipo: TipoItem;
  quantidade_mensal: Decimal;
  valor_unitario_atual: Decimal;
  indice_percentual: Decimal;
  valor_referencial: Decimal | null;
  valor_unitario_reajustado: Decimal;
  subtotal_reajustado: Decimal;
}

export interface Reajuste {
  id: string;
  situacao: 'rascunho' | 'concluido' | 'cancelado';
  sequencia_vigencia: number;
  vigencia_inicio: string;
  vigencia_fim: string;
  mes_referencia: string;
  competencias_recalculadas: number;
  competencias_com_diferenca: number;
  competencia_diferenca: string | null;
  itens: ItemReajuste[];
  base_atual: Decimal;
  base_reajustada: Decimal;
  valor_global_atual: Decimal;
  valor_global_reajustado: Decimal;
  evidencia: Arquivo | null;
  apostilamento: Arquivo | null;
  memorias: { versao: number; criada_em: string; pdf: Arquivo; xlsx: Arquivo }[];
  concluido_em: string | null;
  cancelado_em: string | null;
}

export interface VigenciaDisponivel {
  sequencia: number;
  inicio: string;
  fim: string;
}

export interface PainelReajuste {
  em_andamento: Reajuste | null;
  vigencias_disponiveis: VigenciaDisponivel[];
  historico: Reajuste[];
  pode_editar: boolean;
}

export interface ItemAlteracao {
  item_id: string;
  ordem: number;
  descricao: string;
  tipo: TipoItem;
  valor_unitario: Decimal;
  quantidade_original: Decimal;
  quantidade_executada: Decimal;
  quantidade_nova: Decimal;
  impacto_valor: Decimal;
  abaixo_do_executado: boolean;
}

export interface Alteracao {
  id: string;
  tipo: 'aditamento' | 'supressao';
  situacao: 'rascunho' | 'aguardando_ciencias' | 'concluida' | 'cancelada';
  sequencia_vigencia: number;
  vigencia_inicio: string;
  vigencia_fim: string;
  mes_efeito: string;
  meses_restantes: Decimal;
  itens: ItemAlteracao[];
  valor_global_original: Decimal;
  impacto_valor: Decimal;
  impacto_percentual: Decimal;
  acumulado_percentual: Decimal;
  exige_autorizacao: boolean;
  justificativa: Arquivo | null;
  autorizacao: Arquivo | null;
  de_acordo: Arquivo | null;
  termo: Arquivo | null;
  memoria_pdf: Arquivo | null;
  memoria_xlsx: Arquivo | null;
  consolidado: Arquivo | null;
  ciencias: Ciencia[];
  ciencias_minimas: number;
  concluida_em: string | null;
  cancelada_em: string | null;
}

export interface PainelAlteracao {
  em_andamento: Alteracao | null;
  vigencias: VigenciaDisponivel[];
  historico: Alteracao[];
  pode_editar: boolean;
  integra_equipe: boolean;
}

// --- Painel -----------------------------------------------------------------------------------

export interface Pendencia {
  tipo: string;
  contrato_id: string;
  contrato_numero: string;
  contrato_apelido: string;
  descricao: string;
  rota: string;
  desde: string | null;
}

export interface Risco {
  tipo: string;
  gravidade: 'alta' | 'media';
  descricao: string;
  rota: string;
  data: string | null;
  valor: Decimal | null;
}

/** Riscos agrupados por contrato (só riscos; tarefas ficam em "Minhas pendências"). */
export interface AlertasContrato {
  contrato_id: string;
  contrato_numero: string;
  contrato_apelido: string;
  empresa: string;
  gravidade: 'alta' | 'media';
  riscos: Risco[];
}

export interface PainelContratos {
  hoje: string;
  minhas_pendencias: Pendencia[];
  alertas: AlertasContrato[];
  execucao: {
    exercicio: number;
    meses: { competencia: string; previsto: Decimal; medido: Decimal; pago: Decimal }[];
    total_previsto: Decimal;
    total_medido: Decimal;
    total_pago: Decimal;
    empenhado: Decimal;
    consumido: Decimal;
    saldo_empenho: Decimal;
  };
  numeros: {
    contratos_ativos: number;
    contratos_a_vencer: number;
    contratos_encerrados: number;
    valor_global_ativos: Decimal;
    base_mensal_ativos: Decimal;
  };
  empresas: { id: string; rotulo: string }[];
  contratos: { id: string; rotulo: string }[];
}

// --- Importação do SGI ------------------------------------------------------------------------

export interface EstadoMigracaoSgi {
  situacao: 'ociosa' | 'executando' | 'concluida' | 'erro';
  etapa: string | null;
  mensagem: string;
  origem: string;
  destino: string;
  iniciada_em: string | null;
  concluida_em: string | null;
  iniciada_por: string | null;
  resultado: Record<string, number> | null;
  avisos: string[];
  log: string[];
}
