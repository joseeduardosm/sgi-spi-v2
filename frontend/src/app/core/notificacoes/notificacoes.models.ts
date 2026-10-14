// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados das notificações (caixa de notificações, envio e acompanhamento).

export type Prioridade = 'baixa' | 'normal' | 'alta' | 'critica';
export type Categoria = 'comunicado' | 'prazo' | 'pendencia' | 'revisao' | 'atribuicao' | 'indisponibilidade' | 'normativo';
export type EstadoEntrega = 'nao_visualizada' | 'visualizada' | 'ciente' | 'encerrada';

/** Notificação na caixa de entrada (o `id` é o da entrega). */
export interface EntregaResumo {
  id: string;
  assunto: string;
  prioridade: Prioridade;
  categoria: Categoria;
  autor_nome: string;
  origem: 'avulsa' | 'automatica';
  link: string | null;
  entregue_em: string;
  visualizada_em: string | null;
  ciente_em: string | null;
  encerrada_em: string | null;
  estado: EstadoEntrega;
  pendente: boolean;
  /** Evento do catálogo que originou a notificação (ex.: `contratos.medicao_concluida`). */
  evento: string | null;
  /** A pessoa ligou o canal Desktop para este evento (o cliente Windows alerta só estas). */
  alertar_desktop: boolean;
  /** Contrato ou tarefa a que o aviso se refere: permitem "Silenciar este contrato/tarefa". */
  contrato_id: string | null;
  tarefa_id: string | null;
}

export interface EntregaDetalhe extends EntregaResumo {
  corpo: string;
  abrir_em_janela: boolean;
}

export interface Pagina<T> {
  itens: T[];
  total: number;
  pagina: number;
  tamanho_pagina: number;
}

export interface ResumoCaixa {
  pendentes: number;
  nao_lidas: number;
  janela: EntregaDetalhe | null;
}

export interface OpcaoDestinatario {
  id: number;
  nome: string;
  detalhe: string;
}

export interface Destinatarios {
  usuarios: OpcaoDestinatario[];
  setores: OpcaoDestinatario[];
  pode_enviar_setores: boolean;
}

export interface EnvioNotificacao {
  assunto: string;
  corpo: string;
  prioridade: Prioridade;
  categoria: Categoria;
  usuarios_ids: number[];
  setores_ids: number[];
  expira_em: string | null;
  link: string | null;
}

export interface EnviadaResumo {
  id: string;
  assunto: string;
  prioridade: Prioridade;
  categoria: Categoria;
  publicada_em: string;
  expira_em: string | null;
  destinatarios: number;
  visualizadas: number;
  cientes: number;
}

export interface SituacaoDestinatario {
  usuario_id: number;
  nome: string;
  visualizada_em: string | null;
  ciente_em: string | null;
  encerrada_em: string | null;
  email_enviado_em: string | null;
  email_ok: boolean | null;
  email_erro: string | null;
}

export interface EnviadaDetalhe extends EnviadaResumo {
  corpo: string;
  link: string | null;
  situacao: SituacaoDestinatario[];
}

export const ROTULOS_PRIORIDADE: Record<Prioridade, string> = { baixa: 'Baixa', normal: 'Normal', alta: 'Alta', critica: 'Crítica' };
export const ROTULOS_CATEGORIA: Record<Categoria, string> = {
  comunicado: 'Comunicado', prazo: 'Prazo', pendencia: 'Pendência', revisao: 'Revisão',
  atribuicao: 'Atribuição', indisponibilidade: 'Indisponibilidade', normativo: 'Normativo',
};
export const ROTULOS_ESTADO: Record<EstadoEntrega, string> = {
  nao_visualizada: 'Não lida', visualizada: 'Lida', ciente: 'Ciente', encerrada: 'Resolvida',
};

// --- Preferências ------------------------------------------------------------------------------------------------

export type CanalNotificacao = 'email' | 'navegador' | 'desktop';
export const CANAIS_NOTIFICACAO: CanalNotificacao[] = ['email', 'navegador', 'desktop'];
export const ROTULOS_CANAL: Record<CanalNotificacao, string> = { email: 'E-mail', navegador: 'Navegador', desktop: 'Desktop' };
export type FrequenciaEmail = 'imediato' | 'diario' | 'semanal';

export interface CanalDoEvento { disponivel: boolean; ligado: boolean; obrigatorio: boolean }
export interface EventoPreferencia { chave: string; rotulo: string; descricao: string; canais: Record<CanalNotificacao, CanalDoEvento> }
export interface ModuloPreferencia { chave: string; rotulo: string; eventos: EventoPreferencia[] }
export interface ConfiguracaoNotificacoes {
  frequencia_email: FrequenciaEmail;
  silencio_inicio: string | null;
  silencio_fim: string | null;
  silencio_fins_de_semana: boolean;
}
export interface AparelhoNavegador { id: string; rotulo: string; criada_em: string; ultimo_envio_em: string | null }
export interface SituacaoNavegador {
  disponivel: boolean;
  chave_publica_vapid: string | null;
  inscricoes: number;
  aparelhos: AparelhoNavegador[];
  explicacao: string | null;
}
export interface Silenciado { id: number; tipo: 'contrato' | 'tarefa'; alvo_id: string; rotulo: string }
export interface Preferencias {
  modulos: ModuloPreferencia[];
  configuracao: ConfiguracaoNotificacoes;
  navegador: SituacaoNavegador;
  silenciados: Silenciado[];
}
export interface RespostaTeste { enviado: boolean; detalhe: string }

export interface Obrigatoria {
  id: number;
  evento: string;
  evento_rotulo: string;
  canal: CanalNotificacao;
  setor_id: number | null;
  setor_nome: string | null;
  usuario_id: number | null;
  usuario_nome: string | null;
  criada_em: string;
}
export interface PainelEntregas {
  dias: number;
  por_canal: { canal: CanalNotificacao; enviadas: number; falhas: number }[];
  ultimas_falhas: string[];
  inscricoes_total: number;
  inscricoes_com_falhas: number;
}
