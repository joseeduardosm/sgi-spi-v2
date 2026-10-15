// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o valor por extenso (reais e centavos).

import { describe, expect, it } from 'vitest';

import { valorPorExtenso } from './extenso';

describe('valorPorExtenso', () => {
  it('escreve o exemplo do pedido', () => {
    expect(valorPorExtenso(497982.68)).toBe('Quatrocentos e Noventa e Sete Mil, Novecentos e Oitenta e Dois Reais e Sessenta e Oito Centavos');
  });
  it('trata singular, zero e só centavos', () => {
    expect(valorPorExtenso(1)).toBe('Um Real');
    expect(valorPorExtenso(0.01)).toBe('Um Centavo');
    expect(valorPorExtenso(0)).toBe('Zero Reais');
    expect(valorPorExtenso(2.5)).toBe('Dois Reais e Cinquenta Centavos');
  });
  it('trata cem, cento, mil e as junções com "e"', () => {
    expect(valorPorExtenso(100)).toBe('Cem Reais');
    expect(valorPorExtenso(101)).toBe('Cento e Um Reais');
    expect(valorPorExtenso(1000)).toBe('Mil Reais');
    expect(valorPorExtenso(1100)).toBe('Mil e Cem Reais');
    expect(valorPorExtenso(1025)).toBe('Mil e Vinte e Cinco Reais');
    expect(valorPorExtenso(2350)).toBe('Dois Mil, Trezentos e Cinquenta Reais');
  });
  it('trata milhões e "de reais"', () => {
    expect(valorPorExtenso(1_000_000)).toBe('Um Milhão de Reais');
    expect(valorPorExtenso(3_000_000)).toBe('Três Milhões de Reais');
    expect(valorPorExtenso(8_274_189.1)).toBe('Oito Milhões, Duzentos e Setenta e Quatro Mil, Cento e Oitenta e Nove Reais e Dez Centavos');
  });
});
