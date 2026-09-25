import { HttpErrorResponse } from '@angular/common/http';

/** Erro da API pronto para exibir: mensagem em pt-BR e, quando houver, o código de correlação. */
export interface ErroExibivel {
  mensagem: string;
  codigo: string | null;
  correlacao: string | null;
}

export const MENSAGEM_INDISPONIVEL = 'Serviço indisponível. Tente novamente em instantes.';

/**
 * Converte qualquer erro em mensagem legível. Usa o `detalhe` da API (formato
 * `{"detalhe","codigo"}`) e o cabeçalho `X-Correlacao`, que o suporte usa para achar o log.
 */
export function erroExibivel(erro: unknown): ErroExibivel {
  if (!(erro instanceof HttpErrorResponse)) {
    return { mensagem: 'Ocorreu um erro inesperado.', codigo: null, correlacao: null };
  }
  const corpo = erro.error as { detalhe?: unknown; codigo?: unknown; correlacao?: unknown } | null;
  const correlacao =
    (typeof corpo?.correlacao === 'string' ? corpo.correlacao : null) ?? erro.headers?.get('X-Correlacao') ?? null;
  const codigo = typeof corpo?.codigo === 'string' ? corpo.codigo : null;
  if (typeof corpo?.detalhe === 'string') return { mensagem: corpo.detalhe, codigo, correlacao };
  if (erro.status === 0 || erro.status >= 502) return { mensagem: MENSAGEM_INDISPONIVEL, codigo, correlacao };
  return { mensagem: 'Ocorreu um erro inesperado.', codigo, correlacao };
}
