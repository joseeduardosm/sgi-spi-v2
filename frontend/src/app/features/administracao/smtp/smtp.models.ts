// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados da API de servidores SMTP.

/** Segurança da conexão: STARTTLS (587/25), SSL direto (465) ou sem cifra. */
export type SegurancaSmtp = 'starttls' | 'ssl' | 'nenhuma';

/** Contratos de /api/smtp/servidores (ver docs/endpoints/smtp.md). */
export interface ServidorSmtp {
  id: string;
  nome: string;
  servidor: string;
  porta: number;
  seguranca: SegurancaSmtp;
  usuario: string;
  possui_senha: boolean;
  remetente_email: string;
  remetente_nome: string;
  responder_para: string;
  tempo_limite_segundos: number;
  ativo: boolean;
  ultimo_teste_em: string | null;
  ultimo_teste_ok: boolean | null;
  ultima_latencia_ms: number | null;
  ultimo_erro: string | null;
  ultimo_envio_em: string | null;
  ultimo_envio_ok: boolean | null;
  ultimo_envio_para: string | null;
  ultimo_envio_mensagem: string | null;
  criado_em: string;
  atualizado_em: string;
}

/** Corpo para cadastrar, alterar ou testar sem salvar. */
export interface GravacaoServidorSmtp {
  nome: string;
  servidor: string;
  porta: number;
  seguranca: SegurancaSmtp;
  usuario: string;
  senha: string | null;
  remetente_email: string;
  remetente_nome: string;
  responder_para: string;
  tempo_limite_segundos: number;
  ativo: boolean;
}

/** Resultado de um teste de conexão ou de um envio de teste. */
export interface ResultadoSmtp {
  sucesso: boolean;
  latencia_ms: number;
  mensagem: string;
  id_mensagem: string | null;
}
