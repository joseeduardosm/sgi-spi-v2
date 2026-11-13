/**
 * =============================================================================
 * ARQUIVO: novidades.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Conferir o conteúdo do Changelog: ordem dos dias, a data da bolinha do
 * menu e a linguagem de usuário final dos textos.
 *
 * RESUMO TÉCNICO:
 * Testes unitários (Jasmine: describe/it/expect) sobre as constantes
 * NOVIDADES e MODULOS_NOVIDADE de novidades.ts e ULTIMA_NOVIDADE de
 * core/changelog/ultima-novidade.ts. Não monta componente: só lê dados.
 *
 * FINALIDADE DE NEGÓCIO:
 * Protege a tela Changelog: os dias aparecem do mais novo para o mais antigo,
 * a bolinha de "novidade" do menu acende na data certa e nenhum texto fala
 * em rotas, migrações ou arquivos, que não dizem nada para quem usa o SGI.
 *
 * CONTEXTO NO SISTEMA:
 * Roda com "npx ng test". Quebra quando alguém acrescenta um dia em
 * novidades.ts e esquece de atualizar ultima-novidade.ts, ou usa termo técnico.
 *
 * =============================================================================
 */

import { ULTIMA_NOVIDADE } from '../../core/changelog/ultima-novidade';
import { MODULOS_NOVIDADE, NOVIDADES } from './novidades';

describe('NOVIDADES', () => {
  // Datas no formato AAAA-MM-DD ordenam como texto; por isso sort().reverse() deve devolver a mesma lista.
  it('fica em ordem decrescente de data, sem dia repetido nem dia vazio', () => {
    const datas = NOVIDADES.map((d) => d.data);
    expect(datas.every((d) => /^\d{4}-\d{2}-\d{2}$/.test(d))).toBe(true);
    expect([...datas].sort().reverse()).toEqual(datas);
    expect(new Set(datas).size).toBe(datas.length);
    expect(NOVIDADES.every((d) => d.novidades.length > 0 && d.resumo.trim().length > 0)).toBe(true);
  });

  it('a bolinha do menu usa a data do dia mais recente', () => {
    expect(ULTIMA_NOVIDADE).toBe(NOVIDADES[0].data);
  });

  // Procura em todos os textos (resumo, título, texto e itens) palavras típicas de desenvolvedor
  // e confere que todo módulo citado existe na lista fechada MODULOS_NOVIDADE.
  it('fala com o usuário final: sem rotas da API, migrações nem nomes de arquivo', () => {
    const tecnico = /\/api\/|endpoint|migra[çc][ãa]o [0-9a-f]|alembic|\.py\b|\.ts\b|`/i;
    const textos = NOVIDADES.flatMap((d) => [d.resumo, ...d.novidades.flatMap((n) => [n.titulo, n.texto, ...(n.itens ?? [])])]);
    expect(textos.filter((t) => tecnico.test(t))).toEqual([]);
    expect(NOVIDADES.flatMap((d) => d.novidades).every((n) => MODULOS_NOVIDADE.includes(n.modulo))).toBe(true);
  });
});
