// Criado por José Eduardo Santana Martins
// Este arquivo serve para escolher a densidade de cada coluna do quadro: cartão normal, duas subcolunas, cartão compacto ou cartão reduzido.

/** 1 = cartão normal; 2 = duas subcolunas; 3 = duas subcolunas com cartão compacto; 4 = duas subcolunas com cartão reduzido. */
export type NivelDensidade = 1 | 2 | 3 | 4;

/** Largura mínima (px) da coluna para o nível 2: abaixo disso as subcolunas ficam estreitas demais para o cartão normal. */
export const LARGURA_MINIMA_SUBCOLUNAS = 330;

/** Níveis que a coluna aceita, do menos para o mais denso. */
export function niveisPermitidos(larguraColuna: number): NivelDensidade[] {
  return larguraColuna >= LARGURA_MINIMA_SUBCOLUNAS ? [1, 2, 3, 4] : [1, 4];
}

/**
 * Menor nível em que os cartões cabem na coluna sem rolagem; se nem o mais denso couber, fica nele (a rolagem é o último recurso).
 * `cabe(nivel)` aplica o nível na coluna e diz se o conteúdo coube (o quadro mede `scrollHeight <= clientHeight`).
 */
export function escolherNivel(cabe: (nivel: NivelDensidade) => boolean, larguraColuna: number): NivelDensidade {
  const niveis = niveisPermitidos(larguraColuna);
  for (const nivel of niveis) if (cabe(nivel)) return nivel;
  return niveis[niveis.length - 1];
}
