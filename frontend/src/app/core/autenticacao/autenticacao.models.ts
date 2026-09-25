// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados trocados no login e guardados na sessão.

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

/** Por que a sessão terminou: o usuário clicou em "Sair" ou o token venceu. */
export type MotivoSaida = 'usuario' | 'expirada';
