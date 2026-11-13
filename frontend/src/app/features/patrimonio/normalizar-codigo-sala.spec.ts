/**
 * =============================================================================
 * ARQUIVO: normalizar-codigo-sala.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testes da função normalizarCodigoSala, que lê o código da porta da sala.
 *
 * RESUMO TÉCNICO:
 * Testes com vitest (describe/it/expect): confere que variações de escrita
 * (minúsculas, espaços, hífens, zeros faltando) viram o código padrão, que
 * subsolo (-1) e térreo (00) são tratados e que códigos fora do padrão
 * (áreas comuns) passam só em maiúsculas.
 *
 * FINALIDADE DE NEGÓCIO:
 * Protege a localização correta dos bens: o servidor pode digitar "5a3" ou
 * "05-A-03" e o sistema precisa achar a mesma sala 05A03, sem criar códigos
 * diferentes para o mesmo lugar.
 *
 * CONTEXTO NO SISTEMA:
 * Cobre a função exportada por seletor-sala.component.ts, usada no campo de
 * sala das telas do Patrimônio.
 *
 * =============================================================================
 */

import { describe, expect, it } from 'vitest';

import { normalizarCodigoSala } from './seletor-sala.component';

// describe agrupa os casos; cada it é um cenário e expect compara o resultado.
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
