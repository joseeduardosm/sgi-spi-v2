// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados (interfaces) do módulo de contratos, iguais aos da API.

/**
 * Tipos do módulo de contratos, espelhando os schemas da API (docs/endpoints/contratos-*.md).
 * Valores decimais chegam como texto ("1234.50") para não perder precisão.
 */

/** Valor decimal como texto (ex.: "1234.50"); converter com os formatadores antes de exibir. */
export type Decimal = string;
/** Contínuo (quantidade fixa por mês) ou sob demanda (consumo variável até um teto). */
export type TipoItem = 'continuo' | 'sob_demanda';
/** Situação do contrato na carteira. */
export type Situacao = 'ativo' | 'a_vencer' | 'encerrado' | 'suspenso';
/** Os seis papéis da equipe de gestão e fiscalização (todos com os mesmos poderes). */
export type Papel =
  | 'gestor'
  | 'gestor_suplente'
  | 'fiscal_administrativo'
  | 'fiscal_administrativo_suplente'
  | 'fiscal_tecnico'
  | 'fiscal_tecnico_suplente';
/** Etapas da competência, na ordem do fluxo. */
export type Etapa = 'medicao' | 'avaliacao' | 'nota_fiscal' | 'retencao' | 'cadin' | 'checklist' | 'consolidado' | 'ordem_bancaria' | 'concluida';
/** Situação resumida da competência na lista da aba Execução. */
export type SituacaoCompetencia = 'pendente' | 'disponivel' | 'em_andamento' | 'concluida';

/** Uma página de resultados de uma lista paginada no servidor. */
export interface Pagina<T> {
  itens: T[];
  total: number;
  pagina: number;
  tamanho_pagina: number;
}

/** Referência a um PDF guardado na API (para exibir o nome e montar o download). */
export interface Arquivo {
  anexo_id: string;
  nome: string;
  tamanho: number;
  enviado_em: string;
}

/** Ciência registrada por um integrante da equipe. */
export interface Ciencia {
  usuario_id: number | null;
  nome: string;
  papel: Papel;
  registrada_em: string;
}

// --- Empresas ---------------------------------------------------------------------------------

/** Contrato em que a empresa aparece (número NNN/AAAA). */
export interface ContratoDaEmpresa {
  id: string;
  numero: string;
}

/** Empresa na listagem. */
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

/** Preposto (representante) da empresa. */
export interface Preposto {
  id: string;
  cpf: string;
  nome: string;
  telefone: string;
  email: string;
  cargo: string;
  ativo: boolean;
}

/** Empresa completa, com os prepostos detalhados. */
export interface DetalheEmpresa extends Omit<ResumoEmpresa, 'prepostos'> {
  prepostos: Preposto[];
  criado_em: string;
  atualizado_em: string;
}

/** Empresa em forma reduzida, para o seletor do contrato. */
export interface OpcaoEmpresa {
  id: string;
  cnpj: string;
  razao_social: string;
  nome_fantasia: string;
  ativa: boolean;
}

/** Corpo para cadastrar ou alterar uma empresa. */
export interface GravacaoEmpresa {
  cnpj: string;
  razao_social: string;
  nome_fantasia: string;
  endereco: string;
  ativa: boolean;
}

/** Corpo para cadastrar ou alterar um preposto (tudo menos o id). */
export type GravacaoPreposto = Omit<Preposto, 'id'>;

// --- Contrato ---------------------------------------------------------------------------------

/** Contrato na carteira. */
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

/** Item do contrato, com as quantidades da vigência atual. */
export interface ItemContrato {
  id: string;
  ordem: number;
  descricao: string;
  tipo: TipoItem;
  calcula_pro_rata: boolean;
  /** Unidade de Fornecimento (UF), ex.: posto, hora, unidade. */
  unidade_fornecimento: string;
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

/** Integrante vigente da equipe. */
export interface MembroEquipe {
  papel: Papel;
  usuario_id: number;
  nome: string;
  login: string;
  desde: string | null;
}

/** Uma vigência (a original ou uma prorrogação). */
export interface Vigencia {
  sequencia: number;
  inicio: string;
  fim: string;
  meses: number;
}

/** Marco da linha do tempo da aba Principal. */
export interface Marco {
  data: string;
  tipo: 'inicio' | 'prazo_inicial' | 'termo_aditivo' | 'reajuste' | 'aditamento' | 'supressao' | 'vigencia_atual' | 'maximo';
  rotulo: string;
}

/** Contrato completo, com tudo o que as abas do detalhe exibem. */
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
  // O que o usuário logado pode fazer neste contrato (controla os botões)
  permissoes: { pode_editar: boolean; pode_excluir: boolean };
  // Controle de concorrência: enviar de volta na alteração
  versao: number;
  criado_em: string;
  atualizado_em: string;
}

/** Item no cadastro do contrato (id nulo = item novo). */
export interface GravacaoItem {
  id: string | null;
  descricao: string;
  tipo: TipoItem;
  calcula_pro_rata: boolean;
  /** Unidade de Fornecimento (UF), ex.: posto, hora, unidade. */
  unidade_fornecimento: string;
  codigo_classe: string;
  codigo_natureza_despesa: string;
  codigo_siafisico: string;
  codigo_catmat_catser: string;
  quantidade_mensal: Decimal;
  quantidade_total: Decimal;
  valor_unitario: Decimal;
}

/** Equipe no cadastro: um usuário (id) por papel, ou null. */
export type GravacaoEquipe = Partial<Record<Papel, number | null>>;

/** Corpo do cadastro/edição do contrato. */
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

/** Documento importante do catálogo, anexado ou não. */
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

/** Uma alteração de campo registrada no histórico. */
export interface AlteracaoCampo {
  campo: string;
  de: unknown;
  para: unknown;
  autor: string;
  ocorrido_em: string;
}

// --- Orçamento --------------------------------------------------------------------------------

/** Item dentro de um mês da previsão. */
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

/** Um mês da tabela da previsão. */
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

/** Item sob demanda na grade de apontamentos (quantidade por mês). */
export interface ItemSobDemandaPrevisao {
  item_id: string;
  ordem: number;
  descricao: string;
  limite: Decimal;
  apontamentos: Record<string, Decimal>;
  saldo: Decimal;
}

/** Uma vigência na tela de previsão (grade, selo e total). */
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

/** Resposta completa da previsão. */
export interface Previsao {
  total_previsto: Decimal;
  vigencias: VigenciaPrevisao[];
  meses: MesPrevisao[];
}

/** Lançamento no extrato de uma NE. */
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

/** Nota de Empenho com saldo, reservas e extrato. */
export interface NotaEmpenho {
  id: string;
  numero: string;
  valor_original: Decimal;
  consumido: Decimal;
  saldo: Decimal;
  comprometido: Decimal;
  saldo_livre: Decimal;
  percentual_consumido: Decimal;
  // Cor do cartão conforme o percentual consumido
  faixa: 'verde' | 'amarelo' | 'vermelho';
  vinculada: boolean;
  movimentos: MovimentoNota[];
  criado_em: string;
}

// --- Execução ---------------------------------------------------------------------------------

/** Documento de uma versão do checklist. */
export interface DocumentoChecklist {
  id: string;
  ordem: number;
  nome: string;
  observacao: string;
  /** Obrigatório precisa estar anexado para concluir a etapa; opcional, não. */
  obrigatorio: boolean;
}

/** Versão do checklist do contrato. */
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

/** Uma nota possível da escala de avaliação. */
export interface NotaEscala {
  valor: Decimal;
  legenda: string;
}

/** Faixa de nota que define o % do pagamento liberado. */
export interface FaixaLiberacao {
  minimo: Decimal;
  maximo: Decimal | null;
  percentual: Decimal;
  notas_zero?: number | null;
}

/** Item avaliado dentro de um grupo do formulário. */
export interface ItemFormulario {
  id?: string | null;
  nome: string;
  descricao: string;
  peso: Decimal;
}

/** Grupo de itens do formulário (pesos somam 100%). */
export interface GrupoFormulario {
  id?: string | null;
  nome: string;
  itens: ItemFormulario[];
}

/** Estrutura completa de um formulário de avaliação. */
export interface DefinicaoFormulario {
  escala: NotaEscala[];
  faixas: FaixaLiberacao[];
  grupos: GrupoFormulario[];
}

/** Versão do formulário de avaliação do contrato. */
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

/** Modelo global de checklist ou formulário (conteúdo conforme o tipo). */
export interface Modelo {
  id: string;
  tipo: 'checklist' | 'formulario';
  nome: string;
  conteudo: { itens?: { nome: string; observacao: string; obrigatorio?: boolean }[] } & Partial<DefinicaoFormulario>;
  ativo: boolean;
  atualizado_em: string;
}

/** Competência na lista da aba Execução. */
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

/** Resposta da aba Execução: pré-requisitos e competências por vigência. */
export interface PainelExecucao {
  requisitos: { prontos: boolean; pendencias: string[] };
  geradas: boolean;
  grupos: { sequencia_vigencia: number; inicio: string; fim: string; competencias: ResumoCompetencia[] }[];
}

/** Item medido na competência. */
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
  /** Contínuo: previsto da competência; sob demanda: saldo do item na vigência. */
  saldo: Decimal;
  /** Glosas do diário de bordo com data no período. */
  glosas: Decimal;
  /** Saldo − glosas: o máximo que pode ser medido. */
  saldo_liquido: Decimal;
}

export interface GlosaDoPeriodo {
  ocorrencia_id: string;
  data_ocorrencia: string;
  descricao_ocorrencia: string;
  registrada_por_nome: string;
  item_id: string;
  descricao_item: string;
  quantidade: Decimal;
}

/** Resultado do e-mail enviado à equipe e ao preposto. */
export interface EnvioEmail {
  enviado_em: string | null;
  ok: boolean | null;
  destinatarios: string[];
  erro: string | null;
}

/** NE escolhida (ou disponível) na medição, com o saldo livre. */
export interface NotaSelecionada {
  id: string;
  numero: string;
  saldo: Decimal;
  saldo_livre: Decimal;
}

/** Dados de uma nota fiscal registrada. */
/** Participante da nota (emitente ou tomador), lido do XML. */
export interface ParticipanteNota {
  cnpj: string | null;
  razao_social: string | null;
  inscricao_municipal: string | null;
}

/** Dados da nota lidos do XML (NF-e ou NFS-e), iguais para todos os formatos. */
export interface DadosNotaXml {
  modelo: 'nfe' | 'nfse_nacional' | 'nfse_sp';
  modelo_rotulo: string;
  numero: string | null;
  serie: string | null;
  chave: string | null;
  emissao: string | null;
  competencia: string | null;
  autorizada: boolean | null;
  situacao: string | null;
  emitente: ParticipanteNota;
  tomador: ParticipanteNota;
  valor_bruto: string | null;
  valor_liquido: string | null;
  codigo_servico: string | null;
  discriminacao: string | null;
  itens: { descricao: string; quantidade: string | null; valor_unitario: string | null; valor_total: string | null }[];
  retencoes: Record<Tributo, string>;
  informacoes_complementares: string | null;
}

export type Tributo = 'ir' | 'inss' | 'iss' | 'pis' | 'cofins' | 'csll';

/** Conferência automática da nota (etapa de retenção). */
export interface ConferenciaNota {
  descricao: string;
  situacao: 'ok' | 'alerta' | 'info';
  detalhe: string;
}

export interface NotaFiscal {
  numero: string;
  arquivo: Arquivo | null;
  xml: Arquivo | null;
  dados_xml: DadosNotaXml | null;
  conferencias: ConferenciaNota[];
  valor_bruto: Decimal | null;
  retencao_ir: Decimal;
  retencao_inss: Decimal;
  retencao_iss: Decimal;
  retencao_pis: Decimal;
  retencao_cofins: Decimal;
  retencao_csll: Decimal;
  valor_liquido: Decimal;
}

/** Nota dada a um item na avaliação. */
export interface RespostaAvaliacao {
  item_id: string;
  nota: Decimal;
  justificativa: string;
}

/** Avaliação da competência (etapa 2). */
export interface Avaliacao {
  definicao: DefinicaoFormulario & { grupos: (GrupoFormulario & { id: string; itens: (ItemFormulario & { id: string })[] })[] };
  respostas_iniciais: RespostaAvaliacao[];
  avaliacao_inicial_em: string | null;
  respostas_gestor: RespostaAvaliacao[];
  complemento_gestor: string;
  avaliacao_gestor_em: string | null;
  nota_final: Decimal | null;
  percentual_liberado: Decimal | null;
  // A avaliação do gestor só existe quando alguma nota inicial ficou abaixo da máxima
  precisa_avaliacao_gestor: boolean;
  // Ciências da equipe no ateste (como na medição: uma já libera o PDF)
  ciencias: Ciencia[];
  pdf_gerado: Arquivo | null;
  pdf_assinado: Arquivo | null;
  concluida_em: string | null;
  reconsideracoes: number;
  reconsideracao: Arquivo | null;
}

/** Consulta ao CADIN (etapa 4). */
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

/** Documento do checklist mensal na competência (etapa 5). */
export interface DocumentoMensal {
  id: string;
  ordem: number;
  nome: string;
  observacao: string;
  obrigatorio: boolean;
  arquivo: Arquivo | null;
}

/** Competência completa: tudo o que a tela de execução mostra em todas as etapas. */
export interface DetalheCompetencia extends ResumoCompetencia {
  contrato_id: string;
  contrato_numero: string;
  etapas: Etapa[];
  pode_editar: boolean;
  integra_equipe: boolean;
  // Substituir o consolidado já gerado: só o gestor do contrato ou o SuperRoot
  pode_gerar_consolidado_novamente: boolean;
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
  glosas_periodo: GlosaDoPeriodo[];
  email_medicao: EnvioEmail;
  email_nf: EnvioEmail;
  email_retencao: EnvioEmail;
  retencao: { concluida_em: string | null; por_nome: string; discriminacao_conferida: boolean; pdf: Arquivo | null } | null;
  pode_conferir_retencao: boolean;
  /** Etapas que aceitam gravação agora (depois da NF: retenção, CADIN e checklist em paralelo). */
  etapas_abertas: Etapa[];
  etapas_concluidas: Etapa[];
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

/** Plano de um item sob demanda na nova vigência da prorrogação. */
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

/** Como calcular o limite dos itens sob demanda na prorrogação. */
export type RegraSobDemanda = 'saldo_remanescente' | 'repetir_inicial' | 'manual';

/** Campos do parecer da prorrogação (todos opcionais). */
export interface CamposParecer {
  avaliacao_geral: string;
  resumo_qualidade: string;
  historico_ocorrencias: string;
  reclamacoes: string;
  atendimento_chamados: string;
  parecer: string;
}

/** Rascunho da prorrogação e os dados para montar a tela. */
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

/** Prorrogação registrada (histórico). */
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

/** Item no reajuste: preço atual, índice e preço novo. */
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

/** Reajuste em elaboração ou encerrado. */
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

/** Vigência que pode ser escolhida ao abrir um reajuste ou alteração. */
export interface VigenciaDisponivel {
  sequencia: number;
  inicio: string;
  fim: string;
}

/** Resposta das rotas de reajuste. */
export interface PainelReajuste {
  em_andamento: Reajuste | null;
  vigencias_disponiveis: VigenciaDisponivel[];
  historico: Reajuste[];
  pode_editar: boolean;
}

/** Item na alteração de quantidades. */
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

/** Aditamento ou supressão, com percentuais, documentos e ciências. */
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

/** Resposta das rotas de aditamento/supressão. */
export interface PainelAlteracao {
  em_andamento: Alteracao | null;
  vigencias: VigenciaDisponivel[];
  historico: Alteracao[];
  pode_editar: boolean;
  integra_equipe: boolean;
}

// --- Painel -----------------------------------------------------------------------------------

/** Tarefa do usuário logado, com o link para a tela onde é resolvida. */
export interface Pendencia {
  tipo: string;
  contrato_id: string;
  contrato_numero: string;
  contrato_apelido: string;
  descricao: string;
  rota: string;
  desde: string | null;
}

/** Risco detectado em um contrato. */
export interface Risco {
  tipo: string;
  gravidade: 'alta' | 'media';
  descricao: string;
  rota: string;
  data: string | null;
  valor: Decimal | null;
}

/** Riscos agrupados por contrato (só riscos; tarefas ficam em "Minhas pendências"). */
/** Riscos de um contrato, agrupados. */
export interface AlertasContrato {
  contrato_id: string;
  contrato_numero: string;
  contrato_apelido: string;
  empresa: string;
  gravidade: 'alta' | 'media';
  riscos: Risco[];
}

/** Resposta completa do painel de contratos. */
export interface PainelContratos {
  hoje: string;
  minhas_pendencias: Pendencia[];
  alertas: AlertasContrato[];
  // Execução orçamentária do exercício (gráfico e empenhos)
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
  // Números gerais da carteira
  numeros: {
    contratos_ativos: number;
    contratos_a_vencer: number;
    contratos_encerrados: number;
    valor_global_ativos: Decimal;
    base_mensal_ativos: Decimal;
  };
  // Opções dos filtros do topo do painel
  empresas: { id: string; rotulo: string }[];
  contratos: { id: string; rotulo: string }[];
}

// --- Importação do SGI ------------------------------------------------------------------------

/** Andamento da importação do SGI (a tela consulta periodicamente). */
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

// --- Diário de bordo --------------------------------------------------------------------------

export interface GlosaOcorrencia {
  item_id: string;
  descricao_item: string;
  quantidade: Decimal;
}

export interface OcorrenciaDiario {
  id: string;
  data_ocorrencia: string;
  descricao: string;
  possui_glosa: boolean;
  glosas: GlosaOcorrencia[];
  registrada_por_id: number | null;
  registrada_por_nome: string;
  registrada_por_papel: string;
  criado_em: string;
  competencia_rotulo: string | null;
  medicao_ja_concluida: boolean;
  email: EnvioEmail;
}

export interface DiarioContrato {
  ocorrencias: OcorrenciaDiario[];
  pode_registrar: boolean;
  itens: { id: string; ordem: number; descricao: string; tipo: TipoItem }[];
}

export interface GravacaoOcorrencia {
  data_ocorrencia: string;
  descricao: string;
  possui_glosa: boolean;
  glosas: { item_id: string; quantidade: string }[];
}

// --- Importação por XLSX ----------------------------------------------------------------------

/** Problema da planilha que impede a importação, com a linha em que está. */
export interface ErroImportacao {
  linha: number | null;
  campo: string;
  mensagem: string;
}

/** Item lido de uma linha da tabela de itens da planilha. */
export interface ItemPreviaImportacao {
  linha: number;
  descricao: string;
  tipo: TipoItem | null;
  calcula_pro_rata: boolean | null;
  unidade_fornecimento: string;
  codigo_classe: string;
  codigo_natureza_despesa: string;
  codigo_siafisico: string;
  codigo_catmat_catser: string;
  quantidade_mensal: Decimal | null;
  quantidade_total: Decimal | null;
  valor_unitario: Decimal | null;
}

/** Resposta da prévia: o que será cadastrado, os erros (bloqueiam) e os avisos (só informam). */
export interface PreviaImportacao {
  contrato: {
    numero: string | null;
    apelido: string;
    objeto: string;
    data_inicio: string | null;
    data_fim: string | null;
    vigencia_inicial_meses: number | null;
    vigencia_maxima_meses: number | null;
    periodicidade_meses: number | null;
    mes_reajuste: number | null;
    sei_gestao_numero: string;
    sei_gestao_link: string;
    sei_execucao_numero: string;
    sei_execucao_link: string;
  };
  // Empresa existente é reaproveitada sem alteração; nova será cadastrada
  empresa: { existente: boolean; id: string | null; cnpj: string; razao_social: string; nome_fantasia: string; endereco: string } | null;
  preposto: { existente: boolean; cpf: string; nome: string; email: string; telefone: string } | null;
  itens: ItemPreviaImportacao[];
  valor_global_estimado: Decimal | null;
  erros: ErroImportacao[];
  avisos: string[];
  pode_importar: boolean;
}
