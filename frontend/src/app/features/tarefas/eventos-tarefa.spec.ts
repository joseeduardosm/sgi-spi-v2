// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar os nomes dos dias da visão "O que aconteceu".

import { describe, expect, it } from 'vitest';

import { diaRelativo, rotuloDia } from './eventos-tarefa';

const AGORA = new Date(2026, 9, 13, 15, 0, 0); // terça-feira, 13/10/2026

describe('dias da atividade', () => {
  it('chama o dia de Hoje e Ontem e os demais pelo dia da semana e a data', () => {
    expect(rotuloDia('2026-10-13', AGORA)).toBe('Hoje');
    expect(rotuloDia('2026-10-12', AGORA)).toBe('Ontem');
    expect(rotuloDia('2026-10-09', AGORA)).toBe('sexta-feira, 09/10');
    expect(rotuloDia('2026-09-30', AGORA)).toBe('quarta-feira, 30/09');
  });

  it('calcula o dia relativo atravessando meses e anos', () => {
    expect(diaRelativo(0, AGORA)).toBe('2026-10-13');
    expect(diaRelativo(1, AGORA)).toBe('2026-10-12');
    expect(diaRelativo(29, AGORA)).toBe('2026-09-14');
    expect(diaRelativo(20, new Date(2027, 0, 5))).toBe('2026-12-16');
  });
});
