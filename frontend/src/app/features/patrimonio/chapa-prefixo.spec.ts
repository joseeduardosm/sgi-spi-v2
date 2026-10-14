// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a separação e a junção de prefixo e número da chapa (igual à regra do servidor).

import { describe, expect, it } from 'vitest';

import { montarChapa, separarChapa } from './chapa-prefixo';

const PREFIXOS = [{ codigo: 'SPI' }, { codigo: 'SLT' }, { codigo: 'DERSA' }];

describe('chapa com prefixo', () => {
  it('junta prefixo e número, completando com zeros até 6 dígitos', () => {
    expect(montarChapa('SPI', '231')).toBe('SPI000231');
    expect(montarChapa('slt', '12')).toBe('SLT000012');
    expect(montarChapa('SPI', '1234567')).toBe('SPI1234567');
  });

  it('mantém o texto que não é só número, depois do prefixo, e não repete o prefixo', () => {
    expect(montarChapa('SLT', 'AB-9')).toBe('SLTAB-9');
    expect(montarChapa('SPI', 'SPI000500')).toBe('SPI000500');
    expect(montarChapa('', 'PAT-001')).toBe('PAT-001');
    expect(montarChapa('SPI', '  ')).toBe('');
  });

  it('separa um código lido que já traz o prefixo', () => {
    expect(separarChapa('SPI000231', PREFIXOS)).toEqual({ prefixo: 'SPI', numero: '000231' });
    expect(separarChapa('dersa 55', PREFIXOS)).toEqual({ prefixo: 'DERSA', numero: '55' });
    expect(separarChapa('000231', PREFIXOS)).toBeNull();
    expect(separarChapa('SPI', PREFIXOS)).toBeNull();
  });
});
