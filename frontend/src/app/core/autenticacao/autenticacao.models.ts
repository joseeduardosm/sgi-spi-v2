import { Usuario } from '../modelos/usuario.model';

/** Corpo de `POST /api/autenticacao/login`. */
export interface RequisicaoLogin {
  login: string;
  senha: string;
}

/** Resposta de `POST /api/autenticacao/login`. */
export interface RespostaToken {
  token_acesso: string;
  tipo_token: 'bearer';
  expira_em_segundos: number;
  expira_em: string;
  usuario: Usuario;
}

/** Sessão persistida no navegador. */
export interface SessaoAutenticada {
  tokenAcesso: string;
  expiraEm: number; // epoch em ms
  usuario: Usuario;
}

export type MotivoSaida = 'usuario' | 'expirada';
