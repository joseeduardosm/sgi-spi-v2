// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar as funções de apoio do Painel Executivo (datas e valores dos cartões).

import { dataCurta, emMil, moedaCurta } from './painel-executivo.models';

describe('painel executivo: funções de apoio', () => {
  it('converte reais em milhares', () => {
    expect(emMil('12500.00')).toBe(12.5);
    expect(emMil('0.00')).toBe(0);
  });

  it('formata datas sem mexer em fuso horário', () => {
    expect(dataCurta('2026-10-03')).toBe('03/10');
    expect(dataCurta('2026-10-03', true)).toBe('03/10/2026');
  });

  it('abrevia valores monetários', () => {
    expect(moedaCurta('12300000.00')).toBe('R$ 12,3 mi');
    expect(moedaCurta('45000.00')).toBe('R$ 45 mil');
    expect(moedaCurta('820.50')).toBe('R$ 820,5');
  });
});
