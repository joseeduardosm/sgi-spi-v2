// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos da tela Mensageria (e-mail de changelog).

/** Sugestão do próximo e-mail (`RascunhoChangelog` da API). */
export interface RascunhoChangelog {
  assunto: string;
  corpo: string;
  desde: string | null;
  ate: string | null;
  datas: string[];
  total_destinatarios: number;
}

/** Envio registrado (`EnvioChangelogLeitura` da API). */
export interface EnvioChangelog {
  id: string;
  assunto: string;
  corpo: string;
  destino: 'todos' | 'teste';
  ate_data: string | null;
  total: number;
  enviados: number;
  falhas: number;
  erros: string | null;
  enviado_por_nome: string;
  criado_em: string;
  concluido_em: string | null;
}

/** Pedido de envio (`PedidoEnvioChangelog` da API). */
export interface PedidoEnvioChangelog {
  assunto: string;
  corpo: string;
  destino: 'todos' | 'teste';
  email_teste: string | null;
  ate_data: string | null;
}
