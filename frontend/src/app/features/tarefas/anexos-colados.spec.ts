// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o preparo dos arquivos colados (Ctrl+V) nos comentários das tarefas.

import { describe, expect, it } from 'vitest';

import { prepararArquivosColados } from './anexos-colados';

const AGORA = new Date(2026, 9, 13, 14, 5, 9);
const arquivo = (nome: string, tipo: string) => new File(['x'], nome, { type: tipo });

describe('arquivos colados no comentário', () => {
  it('dá nome de captura ao print colado', () => {
    const r = prepararArquivosColados([arquivo('image.png', 'image/png')], [], AGORA);
    expect(r.arquivos.map((a) => a.name)).toEqual(['captura-20261013-140509.png']);
    expect(r.recusados).toBe(0);
  });

  it('numera vários prints colados de uma vez e mantém o nome dos outros arquivos', () => {
    const r = prepararArquivosColados([arquivo('image.png', 'image/png'), arquivo('relatorio.pdf', 'application/pdf'), arquivo('', 'image/jpeg')], [], AGORA);
    expect(r.arquivos.map((a) => a.name)).toEqual(['captura-20261013-140509-1.png', 'relatorio.pdf', 'captura-20261013-140509-3.jpg']);
  });

  it('recusa formato fora da lista e respeita o limite de 5 arquivos', () => {
    const r = prepararArquivosColados([arquivo('virus.exe', 'application/x-msdownload'), arquivo('a.pdf', 'application/pdf')], [], AGORA);
    expect(r.recusados).toBe(1);
    expect(r.arquivos.map((a) => a.name)).toEqual(['a.pdf']);
    const cheios = Array.from({ length: 4 }, (_, i) => arquivo(`f${i}.txt`, 'text/plain'));
    const excesso = prepararArquivosColados([arquivo('a.pdf', 'application/pdf'), arquivo('b.pdf', 'application/pdf')], cheios, AGORA);
    expect(excesso.arquivos).toHaveLength(5);
    expect(excesso.excedeu).toBe(true);
  });
});
