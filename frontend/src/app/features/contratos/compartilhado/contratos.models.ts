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

/** Contrato em que a empresa aparece (número em formato livre). */
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
  /** Opcional: nulo quando o preposto não tem CPF cadastrado. */
  cpf: string | null;
  nome: string;
  telefone: string;
  email: string;
  cargo: string;
  ativo: boolean;
  /** Representante legal da empresa: signatário do termo aditivo da prorrogação. */
  representante_legal: boolean;
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
export interface CompetenciaAtualCarteira {
  identificador: string;
  rotulo: string;
  situacao: 'pendente' | 'disponivel' | 'em_andamento';
  etapas: string[];
  atrasada: boolean;
}

export interface ResumoContrato {
  id: string;
  numero: string;
  apelido: string;
  empresa_razao_social: string;
  objeto: string;
  criador_id: number | null;
  /** Competência mais antiga ainda não concluída (marcadores da carteira); null se não há. */
  competencia_atual: CompetenciaAtualCarteira | null;
  /** Competências já iniciadas (agosto/2026 em diante): uma linha de marcador `(MM/AAAA - etapa)` cada. */
  competencias_em_andamento?: CompetenciaAtualCarteira[];
  /** A execução do contrato ainda não foi gerada. */
  sem_competencias: boolean;
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
  /** Partes do número quando ele segue NNN/AAAA; nulas nos demais formatos. */
  sequencial: number | null;
  ano: number | null;
  empresa: OpcaoEmpresa;
  data_fim_prazo_inicial: string;
  data_limite_maxima: string;
  vigencia_inicial_meses: number;
  vigencia_maxima_meses: number;
  /** Autoridade do despacho de pagamento (nome, cargo e setor vêm do cadastro do usuário); nulo = não cadastrada. */
  autoridade_despacho: { id: number; nome: string; cargo: string; departamento: string } | null;
  periodicidade_meses: number;
  mes_reajuste: number;
  liberar_todas_competencias: boolean;
  permite_medicao_adicional: boolean;
  /** Competências anteriores a esta data não geram alertas (vale a maior entre ela e o corte global). */
  alertas_a_partir_de: string | null;
  sei_gestao_numero: string;
  sei_gestao_link: string;
  sei_execucao_numero: string;
  sei_execucao_link: string;
  /** Processo financeiro (opcional): é o COD_PROCESSO das OBs no SIGEO (conferência diária da etapa da OB). */
  processo_financeiro: string;
  /** Último pedido do processo ao DOF: quando e quem. */
  processo_financeiro_pedido_em: string | null;
  processo_financeiro_pedido_por: string | null;
  /** Origem da contratação (vazio = não informada) e garantia contratual: alimentam as declarações e as planilhas de garantia da prorrogação. */
  modalidade_contratacao: ModalidadeContratacao;
  exige_garantia: boolean;
  garantia_modalidade: ModalidadeGarantia;
  garantia_percentual: Decimal | null;
  garantia_valor: Decimal | null;
  garantia_emissor: string;
  garantia_cnpj_emissor: string;
  garantia_apolice: string;
  situacao_forcada: Situacao | null;
  vigencias: Vigencia[];
  marcos: Marco[];
  aditamento_acumulado_percentual: Decimal;
  supressao_acumulada_percentual: Decimal;
  itens: ItemContrato[];
  equipe: MembroEquipe[];
  criador_nome: string | null;
  // O que o usuário logado pode fazer neste contrato (controla os botões)
  permissoes: { pode_editar: boolean; pode_excluir: boolean; pode_administrar: boolean; pode_gerir_autoridades: boolean; pode_editar_processo_financeiro: boolean };
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
export type ModalidadeContratacao = '' | 'licitacao' | 'dispensa' | 'inexigibilidade';
export type ModalidadeGarantia = '' | 'caucao_dinheiro' | 'titulos_divida_publica' | 'fianca_bancaria' | 'seguro_garantia' | 'titulo_capitalizacao';

export interface GravacaoContrato {
  numero: string;
  empresa_id: string;
  apelido: string;
  /** Usuário que autoriza o pagamento no despacho do consolidado. */
  autoridade_despacho_id?: number | null;
  objeto: string;
  data_inicio: string;
  vigencia_inicial_meses: number;
  vigencia_maxima_meses: number;
  periodicidade_meses: number;
  mes_reajuste: number;
  liberar_todas_competencias: boolean;
  permite_medicao_adicional: boolean;
  /** Competências anteriores a esta data não geram alertas (vale a maior entre ela e o corte global). */
  alertas_a_partir_de: string | null;
  sei_gestao_numero: string;
  sei_gestao_link: string;
  sei_execucao_numero: string;
  sei_execucao_link: string;
  processo_financeiro: string;
  modalidade_contratacao: ModalidadeContratacao;
  exige_garantia: boolean;
  garantia_modalidade: ModalidadeGarantia;
  garantia_percentual: number | string | null;
  garantia_valor: number | string | null;
  garantia_emissor: string;
  garantia_cnpj_emissor: string;
  garantia_apolice: string;
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

/** NE de cancelamento aplicada a uma NE original. */
export interface CancelamentoNota {
  id: string;
  numero: string;
  valor: Decimal;
  justificativa: string;
  autor: string | null;
  criado_em: string;
}

/** Nota de Empenho com saldo, reservas e extrato. */
export interface NotaEmpenho {
  id: string;
  numero: string;
  valor_original: Decimal;
  consumido: Decimal;
  cancelado: Decimal;
  saldo: Decimal;
  comprometido: Decimal;
  saldo_livre: Decimal;
  percentual_consumido: Decimal;
  // Cor do cartão conforme o percentual consumido
  faixa: 'verde' | 'amarelo' | 'vermelho';
  vinculada: boolean;
  movimentos: MovimentoNota[];
  cancelamentos: CancelamentoNota[];
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
  /** Documento com validade: o envio pede a data e, se ainda valer, ele é reaproveitado na competência seguinte. */
  com_validade: boolean;
  /** Documento da empresa: a execução oferece reaproveitar o igual, ainda válido, de outro contrato da mesma empresa. */
  vale_outros_contratos?: boolean;
  /** Pedir para enviar: o e-mail da medição concluída pede este documento à empresa, com a observação. Editável mesmo com o checklist ativo. */
  pedir_envio?: boolean;
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

/** Máscara da portaria usada quando o contrato tem (ou não) portaria anterior. */
export type VarianteMascara = 'com_anterior' | 'sem_anterior';

/** Documento da prorrogação que uma máscara do tipo `prorrogacao` escreve. */
export type VarianteProrrogacao = 'despacho_instrucao' | 'declaracao_atendimento_licitacao' | 'declaracao_atendimento_direta' | 'minuta_aditivo' | 'termo_ciencia' | 'declaracao_tce' | 'despacho_autorizacao';

/** Tipos de modelo global. */
export type TipoModelo = 'checklist' | 'formulario' | 'portaria' | 'despacho' | 'email_cadin' | 'email_ob' | 'prorrogacao' | 'checklist_prorrogacao';

/** Placeholder permitido nas máscaras de portaria. */
export interface PlaceholderPortaria {
  nome: string;
  descricao: string;
  da_anterior: boolean;
}

/** Modelo global de checklist, formulário ou máscara de portaria (conteúdo conforme o tipo). */
export interface Modelo {
  id: string;
  tipo: TipoModelo;
  nome: string;
  conteudo: { html?: string; assunto?: string; variante?: VarianteMascara | VarianteProrrogacao; itens?: { nome: string; observacao: string; obrigatorio?: boolean; com_validade?: boolean; vale_outros_contratos?: boolean; pedir_envio?: boolean }[] } & Partial<DefinicaoFormulario>;
  ativo: boolean;
  atualizado_em: string;
}

/** Competência na lista da aba Execução. */
export interface ResumoCompetencia {
  id: string;
  competencia: string;
  tipo: 'regular' | 'diferenca_reajuste' | 'adicional';
  /** Número da medição adicional (1, 2…); 0 nas demais. */
  numero_adicional: number;
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
/** Nota de débito, recibo ou outro documento de despesa variável juntado na etapa da nota fiscal. */
export interface DespesaVariavel {
  id: string;
  ordem: number;
  tipo: 'nota_debito' | 'recibo' | 'outros';
  numero: string;
  rotulo: string;
  valor: Decimal;
  arquivo: Arquivo | null;
}

export interface ItemMedicao {
  id: string;
  ordem: number;
  descricao: string;
  /** Trecho do mês (1, 2…) quando o mês tem virada de vigência ou de preço. */
  segmento: number;
  /** Dias do trecho e o que mudou (ex.: "01/09 a 19/09/2026 · preço anterior"); vazio sem virada. */
  periodo_rotulo: string;
  tipo: TipoItem;
  calcula_pro_rata: boolean;
  valor_unitario: Decimal;
  fator_meses: Decimal;
  quantidade_prevista: Decimal;
  quantidade_medida: Decimal;
  /** Acerto de centavos lançado na medição (ex.: 0.01 ou -0.02); soma ao subtotal. */
  acerto: Decimal;
  subtotal: Decimal;
  /** Contínuo: previsto da competência; sob demanda: saldo do item na vigência. */
  saldo: Decimal;
  /** Glosas do diário de bordo com data no período. */
  glosas: Decimal;
  /** Saldo − glosas: o máximo que pode ser medido. */
  saldo_liquido: Decimal;
  /** Item marcado como despesa variável na medição. */
  despesa_variavel?: boolean;
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
export interface Contestacao {
  prazo_dias: number; inicio_em: string; limite_em: string; situacao: 'aberto' | 'vencido' | 'encerrado'; encerrada_em: string | null;
  dias_uteis_decorridos: number; dias_uteis_restantes: number; percentual: number;
  documento_executivo: { anexo_id: string; nome: string; tamanho: number; enviado_em: string } | null; documento_executivo_versao: number;
}

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
  id: string;
  /** Posição da nota na competência (1, 2, …). */
  ordem: number;
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
  /** Ocorrências do diário (no período) que impactam itens desta avaliação: nota máxima nesses itens exige justificativa. */
  ocorrencias: OcorrenciaAvaliacao[];
  /** E-mail do relatório aos prepostos (cópia para a equipe), enviado ao gerar o PDF. */
  email: EnvioEmail;
}

/** Ocorrência do diário de bordo que impacta itens da avaliação. */
export interface OcorrenciaAvaliacao {
  id: string;
  data_ocorrencia: string;
  descricao: string;
  registrada_por_nome: string;
  /** Ids dos itens do formulário desta avaliação. */
  itens: string[];
}

/** Consulta ao CADIN (etapa 4). */
export interface ConsultaCadin {
  id: string;
  possui_pendencia: boolean;
  pendencia: string;
  texto_notificacao: string;
  certidao: Arquivo;
  /** Cópia (PDF) do e-mail enviado pelo sistema aos prepostos. */
  email: Arquivo | null;
  criado_por_nome: string;
  criado_em: string;
  /** Resultado do e-mail da máscara "E-mail de CADIN" (Para: prepostos; Cc: equipe). */
  email_enviado_em: string | null;
  email_ok: boolean | null;
  email_destinatarios: string[];
  email_erro: string | null;
}

/** Documento do checklist mensal na competência (etapa 5). */
export interface DocumentoMensal {
  id: string;
  ordem: number;
  nome: string;
  observacao: string;
  obrigatorio: boolean;
  com_validade: boolean;
  /** Até quando o documento vale (YYYY-MM-DD). */
  validade_ate: string | null;
  /** Mês (YYYY-MM-DD, dia 1) da competência de onde o arquivo foi reaproveitado automaticamente. */
  reaproveitado_de: string | null;
  /** Documento da empresa: pode ser reaproveitado de outro contrato da mesma empresa. */
  vale_outros_contratos?: boolean;
  /** Número do contrato de onde o arquivo foi reaproveitado (só para a tela; o consolidado não mostra). */
  reaproveitado_contrato?: string | null;
  /** Documento igual, ainda válido, de outro contrato da mesma empresa (só com o checklist aberto e o documento sem anexo). */
  sugestao_outro_contrato?: SugestaoOutroContrato | null;
  arquivo: Arquivo | null;
  /** Incluído durante o processo (fora do checklist do contrato): nunca obrigatório e pode ser excluído com a etapa aberta. */
  incluido_no_processo?: boolean;
  incluido_por_nome?: string | null;
  incluido_em?: string | null;
}

/** Documento ainda válido de outro contrato da mesma empresa que pode ser trazido para a competência. */
export interface SugestaoOutroContrato {
  origem_id: string;
  contrato_numero: string;
  /** Mês (YYYY-MM-DD, dia 1) da competência de origem. */
  competencia: string;
  validade_ate: string | null;
  arquivo_nome: string;
}

/** Competência completa: tudo o que a tela de execução mostra em todas as etapas. */
/** Nota fiscal recusada (retrato guardado na recusa; os PDFs continuam disponíveis). */
export interface NotaRecusada {
  rotulo: string;
  numero: string | null;
  valor_bruto: string | null;
  chave: string | null;
  arquivo: Arquivo | null;
  xml: Arquivo | null;
}

/** Recusa da nota fiscal pelo Financeiro: trilha nota → recusa → nova nota → … → aprovação. */
export interface RecusaNota {
  id: string;
  ordem: number;
  justificativa: string;
  recusada_por_nome: string;
  recusada_em: string;
  notas: NotaRecusada[];
  /** PDF da recusa, para juntar a um processo. */
  pdf: Arquivo | null;
  email: EnvioEmail;
}

export interface DetalheCompetencia extends ResumoCompetencia {
  /** O contrato permite medição adicional e o usuário pode incluí-la ("Incluir nova medição"). */
  pode_incluir_adicional: boolean;
  pode_excluir_adicional: boolean;
  /** Medição adicional: justificativa, quem incluiu e o anexo opcional (vazios nas demais). */
  adicional_justificativa: string;
  adicional_por_nome: string;
  adicional_anexo: Arquivo | null;
  contrato_id: string;
  contrato_numero: string;
  /** CNPJ da contratada, só dígitos. */
  empresa_cnpj: string;
  etapas: Etapa[];
  pode_editar: boolean;
  integra_equipe: boolean;
  // Substituir o consolidado já gerado: todos que podem editar o contrato
  pode_gerar_consolidado_novamente: boolean;
  liberada: boolean;
  itens: ItemMedicao[];
  total_previsto: Decimal;
  total_medido: Decimal;
  subtotal_medicao?: Decimal;
  subtotal_despesas_variaveis?: Decimal;
  tem_despesas_variaveis?: boolean;
  despesas_variaveis?: DespesaVariavel[];
  notas_selecionadas: NotaSelecionada[];
  notas_disponiveis: NotaSelecionada[];
  ciencias: Ciencia[];
  ciencias_minimas: number;
  memorias: { versao: number; criada_em: string; arquivo: Arquivo; arquivo_despesas?: Arquivo | null }[];
  medicao_concluida_em: string | null;
  avaliacao: Avaliacao | null;
  percentual_autorizado: Decimal;
  valor_autorizado: Decimal;
  /** Crédito de desconto de reajuste abatido do valor autorizado (0 quando não há). */
  desconto_reajuste: Decimal;
  descontos_reajuste: { reajuste_id: string; mes_referencia: string; valor: Decimal }[];
  valor_a_pagar: Decimal;
  avisos: string[];
  reaberturas_permitidas: boolean;
  glosas_periodo: GlosaDoPeriodo[];
  email_medicao: EnvioEmail;
  /** Prazo de contestação da contratada (dias úteis a contar do e-mail único); nulo antes do envio. Juntar a nota fiscal o encerra. */
  contestacao?: Contestacao | null;
  /** Prazo (dias úteis) informado pelo fiscal ao concluir a medição. */
  prazo_contestacao_dias?: number | null;
  /** Envio solicitado, aguardando a avaliação ser concluída para o e-mail único sair. */
  email_medicao_pendente?: boolean;
  /** Pode reemitir o pacote (contestação aceita) ou repetir um envio que falhou. */
  pode_reemitir_medicao?: boolean;
  email_nf: EnvioEmail;
  /** E-mail aos prepostos avisando que a competência foi paga (enviado ao lançar a OB). */
  email_ob?: EnvioEmail;
  /** Pode anexar a OB e reenviar o e-mail de pagamento (quem edita o contrato ou tem a ação "Lançar ordem bancária"). */
  pode_lancar_ob?: boolean;
  email_retencao: EnvioEmail;
  retencao: { concluida_em: string | null; por_nome: string; discriminacao_conferida: boolean; pdf: Arquivo | null } | null;
  pode_conferir_retencao: boolean;
  /** Recusas da nota fiscal, da primeira para a última. */
  recusas: RecusaNota[];
  /** O usuário pode recusar a nota agora (retenção aberta e permissão de conferir). */
  pode_recusar: boolean;
  /** Etapas que aceitam gravação agora (depois da NF: retenção, CADIN e checklist em paralelo). */
  etapas_abertas: Etapa[];
  etapas_concluidas: Etapa[];
  /** Lançada depois de paga (carga histórica): origem dos dados e itens medidos acima do limite mensal. */
  carga_historica: { em: string; observacao: string; excedentes: string[] } | null;
  /** Competência anterior ao corte de alertas: caminho curto (medição, avaliação se houver, nota fiscal e OB), sem e-mails nem avisos. */
  retroativa: boolean;
  /** Espera a OB e o contrato tem Processo Financeiro: a tela oferece "Buscar a OB no SIGEO". */
  pode_buscar_ob_sigeo: boolean;
  /** Notas fiscais juntadas na etapa 3 (uma ou mais), em ordem. */
  notas_fiscais: NotaFiscal[];
  nf_recebida_em: string | null;
  prazo_pagamento_dias: number | null;
  vencimento_pagamento: string | null;
  origem_valor_nf: 'medicao' | 'manual' | null;
  nf_concluida_em: string | null;
  consultas_cadin: ConsultaCadin[];
  documentos: DocumentoMensal[];
  consolidado: Arquivo | null;
  ordem_bancaria: Arquivo | null;
  /** `manual` (PDF juntado) ou `sigeo` (achada pela conferência diária no SIGEO). */
  ob_origem: 'manual' | 'sigeo' | null;
  ob_numero: string | null;
  ob_data: string | null;
  ob_valor: Decimal | null;
  /** Por que a conferência do SIGEO ainda não concluiu (ex.: pagamento parcial). */
  ob_sigeo_pendencia: string | null;
  ob_sigeo_verificado_em: string | null;
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

/** O que a equipe grava depois da assinatura da prorrogação. */
export interface GravacaoPosAssinatura {
  pncp_publicado_em: string | null;
  pncp_numero: string;
  doe_publicado_em: string | null;
  garantia_comprovada_em: string | null;
  garantia_enviada_dof_em: string | null;
  contratos_gov_atualizado_em: string | null;
  dados_garantia: Record<string, string>;
}

/** Rascunho da prorrogação e os dados para montar a tela (os campos do parecer vêm das telas antigas; a tela nova não os usa). */
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
  /** Memória de cálculo da nova vigência (nula sem prazo salvo). */
  memoria: MemoriaProrrogacao | null;
  /** Versões geradas da memória (PDF e XLSX). */
  memorias: { versao: number; criada_em: string; pdf: Arquivo; xlsx: Arquivo }[];
  /** A última versão gerada corresponde aos dados de agora (exigido para registrar). */
  memoria_atualizada: boolean;
  /** Checklist da prorrogação: o modelo ativo como ponto de partida, mais os documentos incluídos. */
  checklist: DocumentoProrrogacao[];
  obrigatorios_pendentes: number;
}

/** Memória de cálculo da prorrogação: meses, totais por ano e da vigência, e as duas opções dos meses quebrados. */
export interface MemoriaProrrogacao {
  meses: { competencia: string; inicio: string; fim: string; quebrado: boolean; continuos: Decimal; sob_demanda: Decimal; total: Decimal }[];
  totais_por_ano: { ano: number; total: Decimal }[];
  total: Decimal;
  meses_quebrados: { competencia: string; inicio: string; fim: string; dias: number; pro_rata: Decimal; integral: Decimal }[];
  total_pro_rata: Decimal;
  total_integral: Decimal;
  calculo_mes_quebrado: CalculoMesQuebrado | null;
  precisa_escolher: boolean;
}

/** Documento do checklist da prorrogação. */
export interface DocumentoProrrogacao {
  id: string;
  ordem: number;
  nome: string;
  observacao: string;
  obrigatorio: boolean;
  arquivo: Arquivo | null;
  incluido_no_processo: boolean;
  incluido_por_nome?: string | null;
  incluido_em?: string | null;
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
  /** No registro, o checklist do Parecer Referencial tinha item não atendido. */
  precisa_analise_juridica: boolean;
  /** Último dia para divulgar no PNCP (assinatura + 20 dias úteis na licitação, 10 na contratação direta). */
  pncp_prazo_ate: string | null;
  pncp_publicado_em: string | null;
  pncp_numero: string;
  situacao_pncp: 'sem_prazo' | 'publicado' | 'no_prazo' | 'vencido';
  dias_uteis_pncp: number | null;
  doe_publicado_em: string | null;
  exige_garantia: boolean;
  garantia_comprovada_em: string | null;
  garantia_enviada_dof_em: string | null;
  garantia_pendente: boolean;
  dados_garantia: Record<string, string>;
  contratos_gov_atualizado_em: string | null;
  termo: Arquivo | null;
  relatorio: Arquivo | null;
  pode_desfazer: boolean;
}

/** Vigência retroativa cadastrada (anterior ao início do contrato). */
export interface VigenciaRetroativa {
  id: string;
  sequencia: number;
  meses: number;
  assinada_em: string;
  numero_termo: string;
  data_inicio: string;
  data_fim: string;
  codigo_documento: number | null;
  termo: Arquivo | null;
  /** Já tem reajuste retroativo concluído. */
  reajustada: boolean;
  pode_desfazer: boolean;
  motivo_bloqueio: string;
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

/** Como calcular os meses quebrados pela data de efeito: uma escolha para todos os meses e itens do reajuste. */
export type CalculoMesQuebrado = 'pro_rata' | 'integral';

/** Um período do item no mês quebrado (dias antes do efeito sem reajuste, ou a partir dele reajustados). */
export interface TrechoMesQuebrado {
  inicio: string;
  fim: string;
  /** Dias comerciais (30/360). */
  dias: number;
  reajustado: boolean;
  quantidade: Decimal;
  valor_unitario: Decimal;
  valor: Decimal;
}

/** Um item do mês quebrado numa das opções. */
export interface ItemMesQuebrado {
  ordem: number;
  descricao: string;
  quantidade_medida: Decimal;
  valor_pago: Decimal;
  trechos: TrechoMesQuebrado[];
  devido: Decimal;
  em_haver: Decimal;
}

/** Uma opção (pro rata ou integral) de um mês quebrado, com os totais do mês. */
export interface OpcaoMesQuebrado {
  itens: ItemMesQuebrado[];
  valor_pago: Decimal;
  devido: Decimal;
  em_haver: Decimal;
}

/** Mês medido que contém a data de efeito, com as duas opções calculadas. */
export interface MesQuebradoReajuste {
  competencia: string;
  rotulo: string;
  periodo_inicio: string;
  periodo_fim: string;
  opcoes: Record<CalculoMesQuebrado, OpcaoMesQuebrado>;
}

/** Reajuste em elaboração ou encerrado. */
/** Resumo da memória mês a mês: meses medidos (OB paga ou aguardando) e o que ficou em haver. */
export interface ResumoMesesReajuste {
  /** Meses medidos a partir da referência; `paga` = OB concluída, senão medido aguardando a OB. */
  meses: { competencia: string; identificador: string; paga: boolean; valor_pago: Decimal; valor_reajustado: Decimal; em_haver: Decimal }[];
  /** Soma do em haver de todos os meses medidos (= diferença retroativa). */
  total_em_haver: Decimal;
  /** Meses quebrados pela data de efeito, com as duas opções de cálculo. */
  meses_quebrados: MesQuebradoReajuste[];
  /** Diferença retroativa inteira em cada opção. */
  diferenca_pro_rata: Decimal;
  diferenca_integral: Decimal;
  /** Escolha gravada; nula = ainda não escolhida. */
  calculo_mes_quebrado: CalculoMesQuebrado | null;
  /** Há mês quebrado sem escolha: a memória (PDF/XLSX) só é gerada depois dela. */
  precisa_escolher: boolean;
}

export interface Reajuste {
  id: string;
  /** Só em elaboração: a memória mês a mês resumida (os arquivos PDF/XLSX trazem o detalhe item a item). */
  resumo_meses: ResumoMesesReajuste | null;
  situacao: 'rascunho' | 'concluido' | 'cancelado';
  /** Reajuste retroativo (volta no tempo): o preço novo é o da vigência retroativa e o referencial é piso. */
  retroativo: boolean;
  sequencia_vigencia: number;
  vigencia_inicio: string;
  vigencia_fim: string;
  mes_referencia: string;
  /** Data a partir da qual os novos valores valem; o mês dela é pago proporcionalmente aos dias de cada preço. */
  data_efeito: string;
  competencias_recalculadas: number;
  competencias_com_diferenca: number;
  competencia_diferenca: string | null;
  /** Diferença líquida das competências já medidas: > 0 a pagar (competência "-dif"); < 0 crédito da SPI. */
  diferenca_retroativa: Decimal;
  /** Rascunho com desconto retroativo: competência (MM/AAAA) que receberá o crédito. */
  competencia_credito: string | null;
  /** Concluído com desconto retroativo: onde o crédito foi (ou será) abatido. */
  abatimentos: { competencia: string; identificador: string; medida: boolean; valor: Decimal }[];
  credito_pendente: Decimal;
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
  /** Vigências retroativas que aceitam o reajuste retroativo agora (uma por vez, da mais recente para trás). */
  vigencias_retroativas_disponiveis: VigenciaDisponivel[];
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
  // Saldo remanescente e decisões de empenho somados dos contratos visíveis
  orcamento: OrcamentoCarteira;
  // Opções dos filtros do topo do painel
  empresas: { id: string; rotulo: string }[];
  contratos: { id: string; rotulo: string }[];
}

/** Linha do painel de vigências: a vigência de um contrato vigente (escala própria, de `data_inicio` a `data_fim`). */
export interface VigenciaContratoPainel {
  contrato_id: string;
  numero: string;
  rotulo: string;
  empresa: string;
  situacao: 'ativo' | 'a_vencer';
  data_inicio: string;
  data_fim: string;
  dias_restantes: number;
  data_limite_maxima: string;
  meses_prorrogaveis: number;
  vigencias: { sequencia: number; inicio: string; fim: string }[];
  reajustes: string[];
}

/** Resposta do painel de vigências. */
/** Resultado da verificação de um PDF gerado pelo sistema (por código ou por arquivo). */
export interface VerificacaoDocumento {
  valido: boolean;
  motivo: string;
  documento: {
    tipo: string; contrato_id: string; contrato_numero: string; competencia: string | null; gerado_por: string; gerado_em: string;
    codigo: string; sha256: string; ciencias: { nome: string; papel: string; em: string }[];
  } | null;
}

/** Tipos de evento do calendário de vencimentos. */
export type TipoEventoCalendario = 'vigencia_fim' | 'vigencia_maxima' | 'reajuste' | 'pagamento_nf' | 'prazo_nf_48h' | 'validade_documento'
  | 'medicao_atrasada' | 'empenho_insuficiente' | 'tarefa_contrato';

/** Um vencimento ou prazo de contrato numa data (`GET /api/contratos/calendario`). */
export interface EventoVencimento {
  data: string;
  hora?: string | null;
  tipo: TipoEventoCalendario;
  contrato_id: string;
  contrato_numero: string;
  contrato_apelido: string;
  rotulo: string;
  rota: string;
  severidade: 'alta' | 'media' | 'info';
  competencia_id?: string | null;
  valor?: Decimal | null;
}

export interface CalendarioVencimentos { de: string; ate: string; eventos: EventoVencimento[] }

export interface PainelVigencias {
  hoje: string;
  contratos: VigenciaContratoPainel[];
  empresas: { id: string; rotulo: string }[];
}

// --- Importação do SGI ------------------------------------------------------------------------

/** Rascunho de um contrato lido no SGI (POST /contratos/migracao-sgi/rascunho): preenche o cadastro, nada é gravado. */
export interface RascunhoContratoSgi {
  numero: string;
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
  /** `id` preenchido = empresa já cadastrada aqui (pelo CNPJ); nulo = cadastrar pela tela. */
  empresa: { id: string | null; cnpj: string; razao_social: string; nome_fantasia: string; endereco: string; ativa_aqui: boolean };
  prepostos: { cpf: string; nome: string; telefone: string; email: string; cargo: string }[];
  equipe: { papel: Papel; usuario_id: number; login: string; nome: string }[];
  itens: {
    descricao: string; tipo: TipoItem; calcula_pro_rata: boolean; codigo_classe: string; codigo_natureza_despesa: string;
    codigo_siafisico: string; codigo_catmat_catser: string; quantidade_mensal: string; quantidade_total: string; valor_unitario: string;
  }[];
  avisos: string[];
}

// --- Diário de bordo --------------------------------------------------------------------------

export interface GlosaOcorrencia {
  item_id: string;
  descricao_item: string;
  quantidade: Decimal;
}

/** Arquivo anexado à ocorrência do diário. */
export interface AnexoOcorrencia {
  id: string;
  nome: string;
  tamanho: number;
  tipo: string;
}

/** Item do formulário de avaliação que a ocorrência impacta (retrato do nome e do grupo no registro). */
export interface ItemAvaliacaoOcorrencia {
  item_id: string;
  item_nome: string;
  grupo_nome: string;
}

export interface OcorrenciaDiario {
  id: string;
  data_ocorrencia: string;
  descricao: string;
  possui_glosa: boolean;
  glosas: GlosaOcorrencia[];
  anexos: AnexoOcorrencia[];
  impacta_avaliacao: boolean;
  itens_avaliacao: ItemAvaliacaoOcorrencia[];
  registrada_por_id: number | null;
  registrada_por_nome: string;
  registrada_por_papel: string;
  criado_em: string;
  /** Competência afetada pela ocorrência (ex.: 09/2026), não necessariamente a da data. */
  competencia_rotulo: string | null;
  competencia_afetada: string | null;
  medicao_ja_concluida: boolean;
  email: EnvioEmail;
}

export interface DiarioContrato {
  ocorrencias: OcorrenciaDiario[];
  pode_registrar: boolean;
  itens: { id: string; ordem: number; descricao: string; tipo: TipoItem }[];
  /** Itens do formulário de avaliação ativo (vazio sem formulário ativo). */
  itens_avaliacao: { id: string; nome: string; grupo: string }[];
  /** Competências regulares do contrato (mais recente primeiro) para apontar a afetada. */
  competencias: { identificador: string; rotulo: string; periodo_inicio: string; periodo_fim: string; medicao_concluida: boolean }[];
}

export interface GravacaoOcorrencia {
  data_ocorrencia: string;
  /** `AAAA-MM`; vazio = a competência da data. */
  competencia_afetada?: string | null;
  descricao: string;
  possui_glosa: boolean;
  glosas: { item_id: string; quantidade: string }[];
  impacta_avaliacao: boolean;
  itens_avaliacao: string[];
  /** Envia o registro por e-mail à equipe e aos prepostos (padrão: não envia). */
  enviar_email?: boolean;
  /** Prepostos que recebem (nulo = todos os ativos; vazio = só a equipe). */
  prepostos_ids?: string[] | null;
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

// --- Correção de itens (depois de geradas as competências) ------------------------------------

export interface MudancaItemCorrecao {
  item_id: string;
  descricao: string;
  campos: Record<string, { de: string; para: string }>;
}

export interface PreviaCompetenciaCorrecao {
  competencia: string;
  identificador: string;
  itens_alterados: string[];
  itens_incluidos: string[];
  itens_removidos: string[];
  valor_antes: string;
  valor_depois: string;
  variacao: string;
  medicao_iniciada: boolean;
  ciencias_invalidadas: boolean;
}

export interface PreviaCorrecao {
  competencias_abertas: PreviaCompetenciaCorrecao[];
  variacao_total: string;
  congeladas: number;
  fora_do_calendario: number;
  avisos: string[];
}

export interface CorrecaoItens {
  id: string;
  autor_id: number | null;
  autor_nome: string;
  justificativa: string;
  mudancas: MudancaItemCorrecao[];
  previa: PreviaCorrecao;
  situacao: 'pendente' | 'aplicada' | 'recusada' | 'cancelada';
  decidido_por_nome: string;
  decidido_em: string | null;
  motivo_decisao: string;
  criado_em: string;
  pode_decidir: boolean;
  pode_cancelar: boolean;
}

export interface ListaCorrecoes {
  pode_propor: boolean;
  itens: CorrecaoItens[];
}

export interface HistoricoItemContrato {
  id: string;
  item_id: string | null;
  descricao_item: string;
  versao_cadastro: number;
  autor_nome: string;
  motivo: string;
  campos: Record<string, { de: string; para: string }>;
  criado_em: string;
}

// --- Importação de checklist e formulário por XLSX ---------------------------------------------

/** Documento lido de uma linha da planilha do checklist. */
export interface DocumentoPreviaImportacao {
  linha: number;
  nome: string;
  observacao: string;
  obrigatorio: boolean;
  com_validade: boolean;
  vale_outros_contratos?: boolean;
}

/** Prévia da importação de checklist ou formulário (nada foi gravado). */
export interface PreviaImportacaoModelo {
  tipo: 'checklist' | 'formulario';
  nome: string;
  documentos: DocumentoPreviaImportacao[];
  escala: { linha: number; valor: string | null; legenda: string }[];
  faixas: { linha: number; minimo: string | null; maximo: string | null; percentual: string | null; notas_zero: number | null }[];
  grupos: { nome: string; itens: { linha: number; nome: string; descricao: string; peso: string | null }[] }[];
  erros: ErroImportacao[];
  avisos: string[];
  pode_importar: boolean;
}

/** Contrato anterior e próximo na lista da carteira (`VizinhosContrato` da API). */
export interface VizinhosContrato {
  anterior_id: string | null;
  proximo_id: string | null;
  posicao: number | null;
  total: number;
}

// --- Portaria de designação (docs/endpoints/contratos-portarias.md) ---

export type StatusPortaria = 'nomeacao' | 'aguardando_ciencia' | 'aguardando_autoridade' | 'aguardando_aceite' | 'aceita' | 'publicada' | 'cancelada';

export interface AutoridadePortaria {
  id: string;
  sigla: string;
  nome: string;
  cargo: string;
  setor: string;
  usuario_id: number | null;
  usuario_nome: string | null;
  ativa: boolean;
}

export interface GravacaoAutoridade {
  sigla: string;
  nome: string;
  cargo: string;
  setor: string;
  usuario_id: number | null;
  ativa: boolean;
}

/** Usuário do sistema que pode ser a autoridade; cargo e departamento vêm do cadastro dele. */
export interface UsuarioAutoridade {
  id: number;
  login: string;
  nome_completo: string;
  cargo: string;
  departamento: string;
}

/** Função + usuário enviados ao criar ou alterar as nomeações. */
export interface NomeacaoEntrada {
  papel: string;
  usuario_id: number;
}

export interface NomeacaoPortaria {
  papel: string;
  papel_rotulo: string;
  usuario_id: number | null;
  nome: string;
  /** O que falta no cadastro (RS/PV, RG/CIN, cargo): o RH atualiza. Vazio quando completo. */
  dados_pendentes: string[];
  ciente_em: string | null;
}

export interface Portaria {
  id: string;
  titulo: string;
  sigla: string;
  numero: number | null;
  exercicio: number | null;
  status: StatusPortaria;
  status_rotulo: string;
  motivo: string;
  autoridade_nome: string;
  solicitada_por_nome: string;
  solicitada_em: string;
  aceita_por_nome: string | null;
  aceita_em: string | null;
  publicada_em: string | null;
  numero_protocolo_id: string | null;
  anterior: string | null;
  nomeacoes: NomeacaoPortaria[];
  /** Texto da portaria (HTML da máscara), depois da escolha da autoridade. */
  texto_html: string | null;
  pendencias: string[];
  aviso_reserva: string | null;
  tem_evidencia: boolean;
  pode_decidir: boolean;
  pode_alterar: boolean;
  /** Pode anexar o PDF do D.O.E. pela aba Equipe (portaria aceita; quem conduz a portaria). */
  pode_publicar: boolean;
}

export interface PainelPortarias {
  portarias: Portaria[];
  autoridades: AutoridadePortaria[];
  em_andamento: boolean;
  pode_criar: boolean;
  equipe_vigente: NomeacaoEntrada[];
}

/** Nomeação aguardando a ciência do usuário logado (modal ao entrar no sistema). */
export interface CienciaPendente {
  portaria_id: string;
  contrato_id: string;
  contrato: string;
  papel: string;
  papel_rotulo: string;
  nomeado_por: string;
}

export interface ArquivoPagamento {
  anexo_id: string;
  nome: string;
  tamanho: number;
}

/** "Pagamento MM/AAAA" em Documentos Importantes: OB/PD e consolidado da competência. */
export interface PagamentoContrato {
  competencia_id: string;
  titulo: string;
  juntado_em: string;
  ob: ArquivoPagamento;
  consolidado: ArquivoPagamento | null;
}


/** Campos comuns do orçamento executivo (contrato e carteira). */
export interface OrcamentoResumo {
  exercicio: number;
  previsto_concluido: Decimal;
  pago_concluido: Decimal;
  /** Previsto − pago (valor bruto das NFs) dos meses concluídos; negativo = pago acima do previsto. */
  remanescente: Decimal;
  livre: Decimal;
  necessidade: Decimal;
  reforco: Decimal;
  disponivel_cancelar: Decimal;
}

/** Orçamento executivo de um contrato (`GET /contratos/{id}/orcamento-executivo`). */
export interface OrcamentoExecutivo extends OrcamentoResumo {
  meses_concluidos: { competencia: string; previsto: Decimal; pago: Decimal }[];
  empenhado: Decimal;
  meses_restantes: number;
  meses_cobertos: number;
  coberto_ate: string | null;
  primeiro_descoberto: string | null;
  pedir_reforco_ate: string | null;
}

/** Contrato que pede ação no painel: reforço necessário ou empenho sobrando. */
export interface ContratoOrcamento {
  contrato_id: string;
  rotulo: string;
  reforco: Decimal;
  pedir_reforco_ate: string | null;
  disponivel_cancelar: Decimal;
  remanescente: Decimal;
}

/** Orçamento executivo somado da carteira visível no painel. */
export interface OrcamentoCarteira extends OrcamentoResumo {
  precisam_reforco: ContratoOrcamento[];
  com_sobra: ContratoOrcamento[];
}

/** Valores dos parâmetros de Contratos (GravacaoParametrosContratos na API); `padroes` e a auditoria vêm só na leitura. */
export interface ValoresParametrosContratos {
  corte_alertas_a_partir_de: string;
  corte_marcadores_a_partir_de: string;
  dias_pagamento_vencendo: number;
  dias_atraso: number;
  dias_vigencia_a_vencer: number;
  dias_vigencia_atencao: number;
  dias_sem_prorrogacao_alto: number;
  dias_documento_alto: number;
  dias_documento_medio: number;
  dias_fim_vigencia_alto: number;
  dias_fim_vigencia_medio: number;
  vigencia_maxima_padrao_meses: number;
  maximo_meses_vigencia_retroativa: number;
  limite_aditamento_sem_autorizacao: string | number;
  limite_acerto_centavos: string | number;
  maximo_notas_fiscais: number;
  prazo_pagamento_padrao_dias: number;
  prazo_nota_fiscal_horas: number;
  xml_tamanho_maximo_mb: number;
  planilha_tamanho_maximo_mb: number;
  maximo_anexos_ocorrencia: number;
  anexos_email_maximo_mb: number;
  ssgc_nome: string;
  ssgc_cpf: string;
  secretario_nome: string;
  secretario_cpf: string;
  autoridade_competente_nome: string;
  autoridade_competente_cargo: string;
  pncp_dias_uteis_licitacao: number;
  pncp_dias_uteis_direta: number;
  aviso_pncp_dias_uteis: number;
  parecer_referencial_validade_dias: number;
  parecer_referencial_vigencia_ate: string;
}

/** Leitura dos parâmetros: os valores, quem alterou por último e os valores de fábrica ("Restaurar padrão"). */
export interface ParametrosContratos extends ValoresParametrosContratos {
  atualizado_por_nome: string | null;
  atualizado_em: string | null;
  padroes: ValoresParametrosContratos;
}

/** Resultado da busca da OB de uma competência no SIGEO. */
export interface ResultadoBuscaObSigeo {
  concluida: boolean;
  mensagem: string;
}
