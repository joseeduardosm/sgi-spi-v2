// Criado por José Eduardo Santana Martins
// Este arquivo serve para aplicar a configuração do menu (ordem, grupos, nomes, links e itens ocultos) ao menu padrão do código.

import { ItemNavegacao } from './navegacao.model';

/** Nó da configuração do menu (`NoMenu` da API): módulo do código, grupo ou link criado pelo administrador. */
export interface NoMenu {
  id: string;
  tipo: 'modulo' | 'grupo' | 'link';
  rotulo?: string;
  pai_id?: string | null;
  oculto?: boolean;
  url?: string;
  nova_aba?: boolean | null;
}

/** Link criado pelo administrador como item de menu: externo ou em nova aba vira `href`; interno, rota (com a consulta em `destino`). */
export function itemDoLink(no: NoMenu): ItemNavegacao {
  const url = no.url ?? '/';
  const externo = /^https?:\/\//i.test(url);
  const novaAba = no.nova_aba ?? externo;
  if (externo || novaAba) return { id: no.id, rotulo: no.rotulo ?? url, href: url, novaAba };
  return { id: no.id, rotulo: no.rotulo ?? url, rota: url.split('?')[0], destino: url.includes('?') ? url : undefined };
}

interface Entrada {
  id: string;
  no?: NoMenu;
  padrao?: ItemNavegacao;
  paiPadrao: string | null;
}

/**
 * Aplica a configuração do administrador aos itens (já filtrados por papel e ACL). Regras:
 * - itens do código fora da configuração entram no fim, no grupo padrão deles (módulo novo nunca some);
 * - ids da configuração que não existem mais (ou que a pessoa não pode ver) são ignorados;
 * - grupo inexistente ou profundo demais manda o item para o primeiro nível (no máximo dois níveis);
 * - oculto some junto com o que estiver dentro; grupo criado pelo administrador que ficou vazio some.
 * Com `mostrarOcultos` (editor do menu) os ocultos ficam, marcados, e os grupos vazios também.
 */
export function aplicarConfiguracao(itens: ItemNavegacao[], nos: NoMenu[], mostrarOcultos = false): ItemNavegacao[] {
  if (!nos.length && !mostrarOcultos) return itens;
  const padrao = new Map<string, Entrada>();
  const ordemPadrao: string[] = [];
  const percorrer = (lista: ItemNavegacao[], pai: string | null): void => {
    for (const item of lista) {
      padrao.set(item.id, { id: item.id, padrao: item, paiPadrao: pai });
      ordemPadrao.push(item.id);
      if (item.filhos) percorrer(item.filhos, item.id);
    }
  };
  percorrer(itens, null);

  // Entradas na ordem da configuração (módulos desconhecidos saem) e, depois, o que o código tem e a configuração não citou
  const entradas: Entrada[] = [];
  const vistos = new Set<string>();
  for (const no of nos) {
    if (vistos.has(no.id)) continue;
    if (no.tipo === 'modulo') {
      const base = padrao.get(no.id);
      if (!base) continue;
      entradas.push({ ...base, no });
    } else {
      entradas.push({ id: no.id, no, paiPadrao: null });
    }
    vistos.add(no.id);
  }
  for (const id of ordemPadrao) if (!vistos.has(id)) entradas.push(padrao.get(id)!);

  // Pai efetivo: o da configuração (se existir e for primeiro nível) ou o padrão
  const porId = new Map(entradas.map((e) => [e.id, e]));
  const paiDe = (e: Entrada): string | null => (e.no ? (e.no.pai_id ?? null) : e.paiPadrao);
  const eGrupo = (e: Entrada): boolean => e.no?.tipo === 'grupo' || !!e.padrao?.filhos;
  const paiEfetivo = (e: Entrada): string | null => {
    const id = paiDe(e);
    const pai = id ? porId.get(id) : undefined;
    if (!pai || !eGrupo(pai) || pai.id === e.id) return null;
    return paiDe(pai) === null ? pai.id : null;
  };
  // Quem tem filhos não desce de nível (um grupo dentro de grupo passaria dos dois níveis)
  const paiFinal = new Map<string, string | null>();
  for (const e of entradas) paiFinal.set(e.id, paiEfetivo(e));
  for (const e of entradas) if (paiFinal.get(e.id) && entradas.some((o) => paiFinal.get(o.id) === e.id)) paiFinal.set(e.id, null);

  const oculta = (e: Entrada): boolean => !!e.no?.oculto || (!!paiFinal.get(e.id) && oculta(porId.get(paiFinal.get(e.id)!)!));
  const construir = (e: Entrada): ItemNavegacao => {
    let item: ItemNavegacao;
    if (e.no?.tipo === 'grupo') item = { id: e.id, rotulo: e.no.rotulo ?? e.id, icone: 'grade', filhos: [] };
    else if (e.no?.tipo === 'link') item = itemDoLink(e.no);
    else item = { ...e.padrao!, rotulo: e.no?.rotulo || e.padrao!.rotulo, ...(e.padrao!.filhos ? { filhos: [] } : {}) };
    if (mostrarOcultos && oculta(e)) item.oculto = true;
    return item;
  };

  // Primeiro cria todos os itens (o pai pode vir depois do filho na configuração); depois liga cada um ao seu pai, na ordem
  const raiz: ItemNavegacao[] = [];
  const itensPorId = new Map<string, ItemNavegacao>();
  const visiveis = entradas.filter((e) => mostrarOcultos || !oculta(e));
  for (const e of visiveis) itensPorId.set(e.id, construir(e));
  for (const e of visiveis) {
    const pai = paiFinal.get(e.id);
    (pai ? itensPorId.get(pai)?.filhos ?? raiz : raiz).push(itensPorId.get(e.id)!);
  }
  return mostrarOcultos ? raiz : raiz.filter((i) => !(i.filhos && !i.filhos.length && porId.get(i.id)?.no?.tipo === 'grupo'));
}
