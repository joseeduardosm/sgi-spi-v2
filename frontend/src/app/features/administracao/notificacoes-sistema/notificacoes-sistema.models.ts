// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos da tela Notificações do sistema (e-mail de changelog).

/** Sugestão do próximo e-mail (`RascunhoChangelog` da API). */
export interface RascunhoChangelog {
  assunto: string;
  corpo: string;
  desde: string | null;
  ate: string | null;
  datas: string[];
  total_destinatarios: number;
  setores: OpcaoSetorChangelog[];
}

/** Setor que pode receber o e-mail (`OpcaoSetorChangelog` da API). */
export interface OpcaoSetorChangelog {
  id: number;
  nome: string;
  sistemico: boolean;
  nivel: number;
}

export type DestinoChangelog = 'todos' | 'selecionados' | 'teste';

/** Envio registrado (`EnvioChangelogLeitura` da API). */
export interface EnvioChangelog {
  id: string;
  assunto: string;
  corpo: string;
  destino: DestinoChangelog;
  destino_descricao: string | null;
  ate_data: string | null;
  total: number;
  enviados: number;
  falhas: number;
  erros: string | null;
  enviado_por_nome: string;
  criado_em: string;
  agendado_para: string | null;
  cancelado_em: string | null;
  concluido_em: string | null;
  situacao: 'agendado' | 'enviando' | 'concluido' | 'cancelado';
}

/** Pedido de envio (`PedidoEnvioChangelog` da API). */
export interface PedidoEnvioChangelog {
  assunto: string;
  corpo: string;
  destino: DestinoChangelog;
  email_teste: string | null;
  ate_data: string | null;
  usuarios_ids: number[];
  setores_ids: number[];
  /** Instante do envio agendado (ISO com fuso); nulo = envia na hora. */
  agendar_para: string | null;
}
