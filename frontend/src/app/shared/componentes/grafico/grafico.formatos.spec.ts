// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a formatação dos valores dos gráficos.

import { abreviar, descreverSerie, formatarValor } from './grafico.formatos';

describe('formatos de gráfico', () => {
  it('formata números e moeda em pt-BR', () => {
    expect(formatarValor(1234.5, 'numero')).toBe('1.234,5');
    expect(formatarValor(1234.5, 'moeda').replace(/\s/g, ' ')).toBe('R$ 1.234,50');
    expect(formatarValor(12.5, 'moedaMil')).toBe('R$ 12,5 mil');
  });

  it('abrevia valores grandes nos eixos', () => {
    expect(abreviar(1_200_000)).toBe('1,2 mi');
    expect(abreviar(15_000)).toBe('15 mil');
    expect(abreviar(320)).toBe('320');
    expect(abreviar(-2_500)).toBe('-2,5 mil');
  });

  it('descreve a série para leitores de tela', () => {
    expect(descreverSerie('Criadas', ['01/10', '08/10'], [3, 5], 'numero')).toBe('Criadas: 01/10 3, 08/10 5');
  });
});
