// Criado por José Eduardo Santana Martins
// Este arquivo serve para informar a data da novidade mais recente do Changelog (a bolinha do menu), sem carregar o conteúdo todo.

/**
 * Data (AAAA-MM-DD) do dia mais recente em `features/changelog/novidades.ts`.
 *
 * Fica separada para a barra lateral (carregada em toda tela) não precisar do arquivo inteiro de notícias.
 * Ao acrescentar um dia novo às novidades, atualize esta data: o teste `novidades.spec.ts` falha se as duas não baterem.
 */
export const ULTIMA_NOVIDADE = '2026-11-17';
