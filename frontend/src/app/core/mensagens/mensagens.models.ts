// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados da mensageria (caixa de mensagens, envio e acompanhamento).

export type Prioridade = 'baixa' | 'normal' | 'alta' | 'critica';
export type Categoria = 'comunicado' | 'prazo' | 'pendencia' | 'revisao' | 'atribuicao' | 'indisponibilidade' | 'normativo';
export type EstadoEntrega = 'nao_visualizada' | 'visualizada' | 'ciente' | 'encerrada';

/** Mensagem na caixa de entrada (o `id` é o da entrega). */
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
}

export interface EntregaDetalhe extends EntregaResumo {
  corpo: string;
  contrato_id: string | null;
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

export interface EnvioMensagem {
  assunto: string;
  corpo: string;
  prioridade: Prioridade;
  categoria: Categoria;
  usuarios_ids: number[];
  setores_ids: number[];
  expira_em: string | null;
  link: string | null;
  enviar_email: boolean;
}

export interface EnviadaResumo {
  id: string;
  assunto: string;
  prioridade: Prioridade;
  categoria: Categoria;
  publicada_em: string;
  expira_em: string | null;
  enviar_email: boolean;
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
