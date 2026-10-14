// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a leitura do código da porta da sala (variações de escrita viram o mesmo código).

import { describe, expect, it } from 'vitest';

import { normalizarCodigoSala } from './seletor-sala.component';

describe('código da porta da sala', () => {
  it('aceita o código como está e com variações de escrita', () => {
    expect(normalizarCodigoSala('05A03')).toBe('05A03');
    expect(normalizarCodigoSala(' 5a3 ')).toBe('05A03');
    expect(normalizarCodigoSala('05-A-03')).toBe('05A03');
    expect(normalizarCodigoSala('12b15')).toBe('12B15');
  });

  it('trata o subsolo (-1) e o térreo (00)', () => {
    expect(normalizarCodigoSala('-1A1')).toBe('-1A01');
    expect(normalizarCodigoSala('-1A01')).toBe('-1A01');
    expect(normalizarCodigoSala('0b15')).toBe('00B15');
  });

  it('deixa passar o que não é código de sala numerada (áreas comuns e especiais)', () => {
    expect(normalizarCodigoSala('05H')).toBe('05H');
    expect(normalizarCodigoSala('atualizar')).toBe('ATUALIZAR');
  });
});
