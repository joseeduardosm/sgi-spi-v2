// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos da API dos Chamados e os rótulos e cores usados nas telas.

export type StatusBase = 'novo' | 'em_atendimento' | 'pendente' | 'em_aprovacao' | 'solucionado';
export type Prioridade = 'baixa' | 'normal' | 'alta' | 'urgente';
export type TipoChamado = 'incidente' | 'requisicao';
export type FiltroFila = 'abertos' | 'meus' | 'setor' | 'novos' | 'sem_responsavel' | 'sem_itil' | 'solucionados' | 'todos';
export type FiltroMeus = 'abertos' | 'aguardando' | 'resolvidos' | 'todos';
export type ColunaOrdem = 'numero' | 'titulo' | 'solicitante' | 'setor' | 'situacao' | 'prioridade' | 'prazo' | 'aberto_em';
/** Ordenação escolhida clicando no cabeçalho da tabela. */
export interface Ordenacao {
  coluna: ColunaOrdem;
  direcao: 'asc' | 'desc';
}

export interface PapeisChamados {
  abrir: boolean;
  atender: boolean;
  administrar: boolean;
}

export interface SetorResumo {
  id: number;
  nome: string;
  caminho: string;
}

export interface ContextoChamados {
  papeis: PapeisChamados;
  setores_do_usuario: SetorResumo[];
  /** Data em que o SGI passa a receber os chamados de todos ("a partir de"); antes, só Controle total abre aqui. */
  inicio_atendimento?: string | null;
  atendimento_aberto?: boolean;
}

export type TipoCampo = 'texto' | 'texto_longo' | 'numero' | 'data' | 'lista' | 'sim_nao';

/** Campo adicional da categoria (ou herdado de uma categoria acima). */
export interface CampoAdicional {
  id: string;
  rotulo: string;
  ajuda: string | null;
  tipo: TipoCampo;
  obrigatorio: boolean;
  dado_pessoal: boolean;
  opcoes: string[] | null;
  condicao: { campo_id: string; igual: string } | null;
  ordem: number;
}

export interface GravacaoCampo {
  rotulo: string;
  tipo: TipoCampo;
  obrigatorio: boolean;
  dado_pessoal: boolean;
  ajuda: string | null;
  opcoes: string[] | null;
  condicao: { campo_id: string; igual: string } | null;
  ordem: number;
  ativo: boolean;
}

export interface CampoLeitura extends GravacaoCampo {
  id: string;
  categoria_id: string;
}

export interface LocalResumo {
  id: string;
  rotulo: string;
  codigo?: string | null;
  andar?: number | null;
}

export interface ChamadoRelacionavel {
  id: string;
  numero: number;
  titulo: string;
  status_base: StatusBase;
  aberto_em: string;
}

export interface ContextoAbertura {
  local_sugerido: LocalResumo | null;
  relacionaveis: ChamadoRelacionavel[];
}

export interface PessoaResumo {
  id: number;
  nome: string;
  login?: string;
  cargo?: string;
}

export interface AprovacaoPendente {
  id: string;
  chamado_numero: number;
  chamado_titulo: string;
  pedido: string;
  solicitante_nome: string;
  alvo_nome: string;
  criado_em: string;
}

export interface CategoriaCatalogo {
  id: string;
  pai_id: string | null;
  nome: string;
  caminho: string;
  nivel: number;
  permite_incidente: boolean;
  permite_requisicao: boolean;
  perguntar_impedindo: boolean;
  setor_nome: string;
  campos: CampoAdicional[];
}

export interface AberturaChamado {
  titulo: string;
  descricao: string;
  categoria_id: string;
  tipo: TipoChamado;
  impedindo_trabalho: boolean | null;
  setor_solicitante_id: number | null;
  relacionado_id: string | null;
  localizacao_id: string | null;
  /** Porta do switch, quando o chamado é aberto pelo plano de face da rede. */
  rede_porta_id?: string | null;
  campos: Record<string, string>;
}

export interface PrazoSla {
  vence_em: string | null;
  cumprido_em: string | null;
  estourado: boolean;
  percentual: number | null;
  pausado?: boolean;
  /** Cor já calculada pelo servidor com os limites dos Parâmetros. */
  nivel?: NivelPrazo;
}

export interface ChamadoResumo {
  id: string;
  numero: number;
  titulo: string;
  tipo: TipoChamado;
  status_base: StatusBase;
  /** Nome exibido pelos Parâmetros (com o sub-status, se houver) e a cor (token de status). */
  status_nome: string;
  status_cor: CorStatus;
  substatus_id: string | null;
  prioridade: Prioridade;
  prioridade_origem: string;
  categoria_id: string;
  categoria_caminho: string;
  setor_id: number;
  setor_nome: string;
  responsavel_id: number | null;
  responsavel_nome: string;
  solicitante_id: number | null;
  solicitante_nome: string;
  aberto_em: string;
  solucionado_em: string | null;
  atendimento: PrazoSla;
  solucao: PrazoSla;
  importado: boolean;
}

export interface ListaChamados {
  total: number;
  itens: ChamadoResumo[];
}

export interface AnexoChamado {
  id: string;
  nome: string;
  tamanho: number;
  tipo_conteudo: string;
  privado: boolean;
}

export interface ItemLinhaTempo {
  id: string;
  tipo: 'acompanhamento' | 'solucao';
  autor_id: number | null;
  autor_nome: string;
  texto: string;
  privado: boolean;
  automatico: boolean;
  criado_em: string;
  anexos: AnexoChamado[];
}

export interface ChamadoDetalhe extends ChamadoResumo {
  descricao: string;
  impedindo_trabalho: boolean | null;
  setor_solicitante_id: number | null;
  setor_solicitante_nome: string;
  versao: number;
  reabrir_ate: string | null;
  anexos: AnexoChamado[];
  linha_do_tempo: ItemLinhaTempo[];
  acoes: {
    responder: boolean; responder_privado: boolean; assumir: boolean; solucionar: boolean; pendente: boolean; retomar: boolean; nao_resolveu: boolean;
    alterar: boolean; tarefas: boolean; pedir_aprovacao: boolean; incluir_em_copia: boolean;
    /** Quem atende: escolhe a categoria ITIL (também depois de resolvido). */
    classificar?: boolean;
  };
  local: LocalResumo | null;
  relacionado: ChamadoRelacionavel | null;
  campos: { campo_id: string; rotulo: string; valor: string; dado_pessoal: boolean; mascarado: boolean; pode_revelar: boolean }[];
  em_copia: { id: string; usuario_id: number | null; setor_id: number | null; nome: string }[];
  tarefas: TarefaChamado[];
  validacoes: ValidacaoChamado[];
  reaberturas: number;
  pendente_desde: string | null;
  satisfacao?: SatisfacaoChamado | null;
  /** Classificação técnica: só vem para quem atende (nula = pendente). */
  categoria_itil_id?: string | null;
  categoria_itil?: string;
}

export interface TarefaChamado {
  id: string;
  texto: string;
  estado: 'a_fazer' | 'feita';
  privada: boolean;
  responsavel_id: number | null;
  responsavel_nome: string;
  autor_nome: string;
  criado_em: string;
  feita_em: string | null;
}

export interface ValidacaoChamado {
  id: string;
  status: 'aguardando' | 'aprovada' | 'recusada';
  alvo_nome: string;
  pedido: string;
  resposta: string;
  solicitante_nome: string;
  respondida_por_nome: string;
  criado_em: string;
  respondida_em: string | null;
  posso_responder: boolean;
}

/** O que o `PATCH /chamados/{numero}` aceita (só os campos enviados mudam). */
export interface AlteracaoChamado {
  versao: number;
  categoria_id?: string;
  setor_id?: number;
  responsavel_id?: number | null;
  prioridade?: Prioridade;
  motivo_prioridade?: string;
  substatus_id?: string | null;
}

// --- Parâmetros do marco 3 ---

export type CorStatus = 'info' | 'alerta' | 'atencao' | 'perigo' | 'sucesso' | 'neutro';
export const ROTULOS_COR: Record<CorStatus, string> = {
  info: 'Azul (informação)', alerta: 'Âmbar (alerta)', atencao: 'Laranja (atenção)', perigo: 'Vermelho (perigo)', sucesso: 'Verde (sucesso)', neutro: 'Cinza (neutro)',
};

export interface ParametrosGerais {
  /** Atendimento no SGI a partir desta data (AAAA-MM-DD); nula = sem data marcada. */
  inicio_atendimento: string | null;
  dias_reabrir: number;
  ponto_facultativo_util: boolean;
  limite_alerta: number;
  limite_atencao: number;
  limite_perigo: number;
}

export interface StatusApresentacao {
  status_base: StatusBase;
  nome: string;
  cor: CorStatus;
}

export interface Substatus {
  id: string;
  status_base: StatusBase;
  nome: string;
  cor: CorStatus;
  ordem: number;
  ativo: boolean;
}

export interface SetorAtendimento {
  setor_id: number;
  nome: string;
  caminho: string;
  ve_todos: boolean;
}

export interface GravacaoRecorrente {
  nome: string;
  categoria_id: string;
  titulo: string;
  descricao: string;
  periodicidade_quantidade: number;
  periodicidade_unidade: 'dia' | 'semana' | 'mes';
  antecedencia_min: number;
  so_dias_uteis: boolean;
  proxima_em: string;
  fim_em: string | null;
  ativo: boolean;
  solicitante_id: number | null;
}

export interface Recorrente extends GravacaoRecorrente {
  id: string;
  categoria_caminho: string;
  solicitante_nome: string;
  ultima_geracao_em: string | null;
}

export interface SaudeChamados {
  tarefas: { tarefa: string; ultima_em: string | null; ultimo_estado: string | null; ultima_ok_em: string | null; ultimo_erro: string | null; ultimo_resumo: string }[];
  email_parados: number;
  email_falhas_24h: number;
  email_mais_antigo: string | null;
  ultimo_erro_email: string | null;
  problemas: string[];
}

// --- Parâmetros ---------------------------------------------------------------------------------------------------------

export interface FaixaExpediente {
  dia_semana: number;
  inicio: string;
  fim: string;
}

export interface Expediente {
  id: string;
  nome: string;
  ativo: boolean;
  faixas: FaixaExpediente[];
}

export interface Sla {
  id: string;
  nome: string;
  tipo: 'tto' | 'ttr';
  tempo: number;
  unidade: 'minuto' | 'hora' | 'dia';
  expediente_id: string;
  expediente_nome: string;
  ativo: boolean;
}

export interface GravacaoCategoria {
  nome: string;
  pai_id: string | null;
  ativa: boolean;
  visivel_solicitante: boolean;
  permite_incidente: boolean;
  permite_requisicao: boolean;
  setor_id: number | null;
  responsavel_id: number | null;
  sla_tto_id: string | null;
  sla_ttr_id: string | null;
  prioridade_padrao: Prioridade | null;
  perguntar_impedindo: boolean;
  sigilosa: boolean;
  ordem: number;
  /** Categoria ITIL que o chamado recebe ao abrir neste assunto (vazio = herda da mãe ou fica pendente para o técnico). */
  categoria_itil_id: string | null;
  /** "Quem pode escolher este assunto": só os membros destes setores (vazio = qualquer pessoa ou só quem atende). */
  setores_permitidos: number[];
}

/** Categoria ITIL: a classificação técnica (separada do assunto que quem abre escolhe). */
export interface GravacaoCategoriaItil { nome: string; pai_id: string | null; ativa: boolean; ordem: number }
export interface CategoriaItil extends GravacaoCategoriaItil { id: string; caminho: string; nivel: number; chamados: number }
export interface CategoriaItilResumo { id: string; caminho: string }

export interface Categoria extends GravacaoCategoria {
  id: string;
  caminho: string;
  nivel: number;
  setor_efetivo_id: number | null;
  setor_efetivo_nome: string;
  herda_setor: boolean;
}

// --- Rótulos -------------------------------------------------------------------------------------------------------------

/** Nome do status para quem atende. */
export const ROTULOS_STATUS: Record<StatusBase, string> = {
  novo: 'Novo',
  em_atendimento: 'Em atendimento',
  pendente: 'Pendente',
  em_aprovacao: 'Em aprovação',
  solucionado: 'Resolvido',
};

/** Nome do status para quem pediu (linguagem simples). */
export function rotuloStatusSolicitante(c: Pick<ChamadoResumo, 'status_base' | 'setor_nome' | 'responsavel_nome'>): string {
  switch (c.status_base) {
    case 'novo':
      return `Aguardando ${c.setor_nome}`;
    case 'em_atendimento':
      return c.responsavel_nome ? `Com ${c.responsavel_nome}` : `Com ${c.setor_nome}`;
    case 'pendente':
      return 'Aguardando você';
    case 'em_aprovacao':
      return 'Em aprovação';
    default:
      return 'Resolvido';
  }
}

/** Cor (token de status) do selo de cada status-base. */
export const COR_STATUS: Record<StatusBase, 'info' | 'alerta' | 'sucesso'> = {
  novo: 'info',
  em_atendimento: 'info',
  pendente: 'alerta',
  em_aprovacao: 'info',
  solucionado: 'sucesso',
};

export const ROTULOS_PRIORIDADE: Record<Prioridade, string> = { baixa: 'Baixa', normal: 'Normal', alta: 'Alta', urgente: 'Urgente' };
export const ROTULOS_TIPO: Record<TipoChamado, string> = { incidente: 'Incidente (algo parou de funcionar)', requisicao: 'Requisição (pedido de serviço)' };
export const DIAS_SEMANA = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
export const ROTULOS_UNIDADE: Record<Sla['unidade'], string> = { minuto: 'minutos', hora: 'horas', dia: 'dias úteis' };
export const ROTULOS_TIPO_CAMPO: Record<TipoCampo, string> = {
  texto: 'Texto curto', texto_longo: 'Texto longo', numero: 'Número', data: 'Data', lista: 'Lista de opções', sim_nao: 'Sim ou não',
};

/** O campo aparece? Sem condição, sempre; com condição, quando o outro campo tem o valor pedido (como no servidor). */
export function campoVisivel(campo: CampoAdicional, respostas: Record<string, string>): boolean {
  if (!campo.condicao) return true;
  return (respostas[campo.condicao.campo_id] ?? '').trim().toLowerCase() === campo.condicao.igual.trim().toLowerCase();
}

/** Limites do painel e dos selos de prazo (% do SLA consumido). Parametrizáveis no marco do painel de TV. */
export const LIMITES_SLA = { alerta: 50, atencao: 75, perigo: 90 };

export type NivelPrazo = 'sem' | 'ok' | 'alerta' | 'atencao' | 'perigo' | 'cumprido';

/** Nível de cor de um prazo: cumprido = verde; senão, pela parte já consumida (50 âmbar, 75 laranja, 90 vermelho). */
export function nivelPrazo(prazo: PrazoSla): NivelPrazo {
  // O servidor já calcula com os limites dos Parâmetros; o cálculo local só vale para respostas antigas
  if (prazo.nivel) return prazo.nivel;
  if (!prazo.vence_em) return 'sem';
  if (prazo.cumprido_em) return prazo.estourado ? 'perigo' : 'cumprido';
  if (prazo.estourado) return 'perigo';
  const p = prazo.percentual ?? 0;
  if (p >= LIMITES_SLA.perigo) return 'perigo';
  if (p >= LIMITES_SLA.atencao) return 'atencao';
  if (p >= LIMITES_SLA.alerta) return 'alerta';
  return 'ok';
}

/** Texto do prazo, sempre junto da cor (a cor nunca é o único sinal). */
export function textoPrazo(prazo: PrazoSla): string {
  if (!prazo.vence_em) return 'Sem prazo';
  if (prazo.pausado) return `Pausado em ${prazo.percentual ?? 0}%`;
  if (prazo.cumprido_em) return prazo.estourado ? 'Cumprido com atraso' : 'Cumprido no prazo';
  if (prazo.estourado) return 'Prazo estourado';
  return `${prazo.percentual ?? 0}% do prazo`;
}

/** Data e hora em São Paulo (dd/mm/aaaa hh:mm). */
export function dataHora(valor: string | null): string {
  if (!valor) return '';
  return new Date(valor).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** Tamanho legível (KB/MB). */
export function tamanhoLegivel(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

// ---------------------------------------------------------------------------------------------
// Marco 4: painel de TV, TVs pareadas e chamados do RH
// ---------------------------------------------------------------------------------------------

/** Cor da linha do painel: o pior dos dois prazos; `resolvido` = verde (sai depois de alguns minutos). */
export type NivelPainel = 'sem' | 'ok' | 'alerta' | 'atencao' | 'perigo' | 'resolvido';

export interface ItemPainel {
  numero: number; titulo: string; solicitante: string; responsavel: string; local: string; setor_nome: string;
  aberto_em: string; solucionado_em: string | null; status_base: StatusBase; status_nome: string; prioridade: Prioridade;
  nivel: NivelPainel; percentual: number | null; estourado: boolean; pausado: boolean;
}

export interface EstadoPainel {
  area: string; gerado_em: string; config: ConfigPainel; limites: { alerta: number; atencao: number; perigo: number };
  indicadores: { abertos: number; sem_responsavel: number; estourados: number; resolvidos_hoje: number };
  itens: ItemPainel[];
}

/** Colunas que o painel pode mostrar (Parâmetros > Painel). */
export type ColunaPainel = 'abertura' | 'titulo' | 'usuario' | 'local' | 'espera' | 'situacao' | 'responsavel';
export interface ConfigPainel {
  linhas_por_pagina: number; tamanho: 'compacto' | 'normal' | 'grande'; segundos_pagina: number; voz: boolean; cor_linha: boolean;
  colunas: ColunaPainel[];
}

/** Fila, prioridade e prazos de um serviço do RH (Nomeação ou Exoneração). */
export interface ConfigServicoRh { setor_id: number | null; prioridade: Prioridade; sla_tto_id: string | null; sla_ttr_id: string | null }
export interface ServicoRh extends ConfigServicoRh { servico: string; rotulo: string; setor_nome: string }
/** `na_data`: GLPI até a data "a partir de" e, nesse dia, o SGI; `destino_atual` diz para onde vai agora. */
export interface ParametrosRh { destino: 'glpi' | 'chamados' | 'na_data'; destino_atual: 'glpi' | 'chamados'; servicos: ServicoRh[]; servicos_exoneracao: ServicoRh[] }

/** Evento ao vivo: a tela busca de novo o que mostra. */
/** Aviso ao vivo. `acao`: o que aconteceu de marcante (o painel anuncia por voz); vazio = outra mudança. */
export interface EventoChamado { tipo: 'novo' | 'alterado'; numero: number; acao?: '' | 'assumido' | 'resolvido' | 'reaberto' | 'transferido' }

/** Texto da coluna "Situação" do painel (a cor nunca é o único sinal). */
export function textoNivelPainel(item: ItemPainel): string {
  if (item.nivel === 'resolvido') return 'Resolvido';
  if (item.pausado) return 'Pendente';
  if (item.estourado) return 'Prazo estourado';
  if (item.percentual === null) return 'Sem prazo';
  return `${item.percentual}% do prazo`;
}

/** Tempo desde a abertura: "34 min", "3h12", "2 dias". */
export function tempoEspera(abertoEm: string, agora: number): string {
  const minutos = Math.max(0, Math.floor((agora - new Date(abertoEm).getTime()) / 60000));
  if (minutos < 60) return `${minutos} min`;
  if (minutos < 24 * 60) return `${Math.floor(minutos / 60)}h${String(minutos % 60).padStart(2, '0')}`;
  const dias = Math.floor(minutos / (24 * 60));
  return dias === 1 ? '1 dia' : `${dias} dias`;
}

/** Hora (hh:mm) em São Paulo; de outro dia, "dd/mm hh:mm". */
export function horaPainel(valor: string, agora: number): string {
  const data = new Date(valor);
  const fuso = { timeZone: 'America/Sao_Paulo' } as const;
  const mesmoDia = data.toLocaleDateString('pt-BR', fuso) === new Date(agora).toLocaleDateString('pt-BR', fuso);
  const hora = data.toLocaleTimeString('pt-BR', { ...fuso, hour: '2-digit', minute: '2-digit' });
  return mesmoDia ? hora : `${data.toLocaleDateString('pt-BR', { ...fuso, day: '2-digit', month: '2-digit' })} ${hora}`;
}

// ---------------------------------------------------------------------------------------------
// Marco 6: satisfação, respostas prontas, motivos de pendência e relatórios
// ---------------------------------------------------------------------------------------------

export interface SatisfacaoChamado { nota: number | null; rotulo: string; comentario: string; respondida_em: string | null; pode_avaliar: boolean }

/** As cinco notas, com rótulo em texto (decisão de design: 5 botões com rótulo, sem estrelas). */
export const NOTAS_SATISFACAO: [number, string][] = [[1, 'Péssimo'], [2, 'Ruim'], [3, 'Regular'], [4, 'Bom'], [5, 'Ótimo']];

export interface RespostaPronta { id: string; titulo: string; texto: string; setor_id: number | null; setor_nome: string; ativo: boolean; ordem: number }
export type GravacaoRespostaPronta = Omit<RespostaPronta, 'id' | 'setor_nome'>;
export interface MotivoPendencia { id: string; nome: string; ativo: boolean; ordem: number }

export interface LinhaRelatorio { /** Categoria (uuid) ou setor (número) da linha, para abrir a lista. */ id: string; nome: string; abertos: number; resolvidos: number; no_prazo_pct: number | null }
export interface RelatorioChamados {
  area: string; inicio: string; fim: string;
  resumo: {
    abertos_no_periodo: number; resolvidos_no_periodo: number; em_aberto_agora: number;
    atendimento_no_prazo: number; atendimento_com_prazo: number; atendimento_no_prazo_pct: number | null;
    solucao_no_prazo: number; solucao_com_prazo: number; solucao_no_prazo_pct: number | null;
    horas_mediana_solucao: number | null; reabertos: number; satisfacao_media: number | null; satisfacao_respostas: number; satisfacao_pedidas: number;
  };
  semanas: {
    inicio: string; abertos: number; resolvidos: number; em_aberto_fim: number; reabertos: number; horas_mediana_solucao: number | null;
    atendimento_no_prazo_pct: number | null;
  }[];
  por_categoria: LinhaRelatorio[]; por_setor: LinhaRelatorio[]; por_prioridade: Record<string, number>; notas: number[];
  /** Quanto cada pessoa rendeu (resolvidos e assumidos) em três janelas. */
  equipe: PessoaEquipe[];
  /** Controle total ou líder de setor com setores abaixo: escolhe o setor e vê a quebra por setor. */
  pode_escolher_setor: boolean;
  setores_opcoes: { id: number; nome: string }[];
}
export interface PessoaEquipe {
  usuario_id: number; nome: string; resolvidos_7d: number; assumidos_7d: number; resolvidos_30d: number; assumidos_30d: number;
  resolvidos_semana: number; assumidos_semana: number;
}

/** Migração do GLPI pelo botão (Parâmetros, só Controle total). */
export interface ConfiguracaoMigracaoGlpi {
  ativa: boolean; host: string; porta: number; banco: string; usuario: string; setor_padrao_id: number | null;
  /** Traz só os chamados não solucionados (padrão). */
  so_abertos: boolean;
}
export interface AndamentoMigracaoGlpi {
  modo?: 'novidades' | 'refazer'; situacao?: 'em_andamento' | 'concluido' | 'erro'; etapa?: string; mensagem?: string; percentual?: number;
  chamados_migrados?: number; chamados_total?: number | null; iniciado_em?: string; atualizado_em?: string; autor?: string;
  resumo?: { versao: string; novos: number; atualizados: number; sem_mudanca: number; trabalhados_sgi?: number; resolvidos_nao_migrados?: number; categorias_itil: number; acompanhamentos: number; solucoes: number;
    avisos: string[]; total_avisos: number } | null;
}
export interface LeituraMigracaoGlpi extends ConfiguracaoMigracaoGlpi {
  senha_cadastrada: boolean; ultima_sincronizacao: string | null; andamento: AndamentoMigracaoGlpi;
}

