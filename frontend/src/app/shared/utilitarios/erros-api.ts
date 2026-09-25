// Criado por José Eduardo Santana Martins
// Este arquivo serve para transformar erros das chamadas à API em mensagens legíveis para o usuário.

import { HttpErrorResponse } from '@angular/common/http';

/** Erro da API pronto para exibir: mensagem em pt-BR e, quando houver, o código de correlação. */
export interface ErroExibivel {
  mensagem: string;
  codigo: string | null;
  correlacao: string | null;
}

// Mensagem usada quando a API não responde (fora do ar, gateway com erro)
export const MENSAGEM_INDISPONIVEL = 'Serviço indisponível. Tente novamente em instantes.';

/**
 * Converte qualquer erro em mensagem legível. Usa o `detalhe` da API (formato
 * `{"detalhe","codigo"}`) e o cabeçalho `X-Correlacao`, que o suporte usa para achar o log.
 */
export function erroExibivel(erro: unknown): ErroExibivel {
  // Erro que não veio de uma chamada HTTP (ex.: falha de código no navegador)
  if (!(erro instanceof HttpErrorResponse)) {
    return { mensagem: 'Ocorreu um erro inesperado.', codigo: null, correlacao: null };
  }
  // Corpo de erro da API; os campos são conferidos um a um, pois o formato pode não ser o esperado
  const corpo = erro.error as { detalhe?: unknown; codigo?: unknown; correlacao?: unknown } | null;
  // A correlação pode vir no corpo (erros 500) ou no cabeçalho X-Correlacao
  const correlacao =
    (typeof corpo?.correlacao === 'string' ? corpo.correlacao : null) ?? erro.headers?.get('X-Correlacao') ?? null;
  const codigo = typeof corpo?.codigo === 'string' ? corpo.codigo : null;
  if (typeof corpo?.detalhe === 'string') return { mensagem: corpo.detalhe, codigo, correlacao };
  // status 0 = sem resposta (rede); 502+ = proxy sem acesso à API
  if (erro.status === 0 || erro.status >= 502) return { mensagem: MENSAGEM_INDISPONIVEL, codigo, correlacao };
  return { mensagem: 'Ocorreu um erro inesperado.', codigo, correlacao };
}
