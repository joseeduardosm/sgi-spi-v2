// Criado por José Eduardo Santana Martins
// Este arquivo serve para achatar o menu lateral numa lista de telas (rótulo e rota), usada pela busca global e pela paleta de comandos.

import { ItemNavegacao, SecaoNavegacao } from './navegacao.model';

/** Uma tela do menu: o que a pessoa lê e para onde vai. */
export interface TelaMenu {
  id: string;
  titulo: string;
  rota: string;
}

/** Minúsculas e sem acento, para comparar textos. */
export function normalizarTexto(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

/** Todas as telas com rota interna (grupos entram pelos filhos); o menu já vem filtrado por papel e ACL. */
export function telasDoMenu(secoes: readonly SecaoNavegacao[]): TelaMenu[] {
  const achatar = (itens: readonly ItemNavegacao[]): TelaMenu[] =>
    itens.flatMap((i) => [...(i.rota ? [{ id: i.id, titulo: i.rotulo, rota: i.destino ?? i.rota }] : []), ...achatar(i.filhos ?? [])]);
  return achatar(secoes.flatMap((s) => s.itens));
}
