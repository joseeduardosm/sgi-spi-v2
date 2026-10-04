// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar as funções de apoio do Diretório (iniciais, datas e selo de férias).

import { dataBr, diaMes, iniciais, quando, seloFerias } from './diretorio.models';

describe('diretório: funções de apoio', () => {
  it('monta as iniciais do primeiro e do último nome', () => {
    expect(iniciais('Bia Souza')).toBe('BS');
    expect(iniciais('maria da Silva Santos')).toBe('MS');
    expect(iniciais('Célia')).toBe('C');
    expect(iniciais('   ')).toBe('?');
  });

  it('formata dia/mês e datas', () => {
    expect(diaMes(3, 7)).toBe('03/07');
    expect(dataBr('2026-10-03')).toBe('03/10/2026');
  });

  it('descreve quando é o aniversário', () => {
    expect(quando(0)).toBe('Hoje');
    expect(quando(1)).toBe('Amanhã');
    expect(quando(5)).toBe('Em 5 dias');
    expect(quando(-1)).toBe('Ontem');
    expect(quando(-4)).toBe('Há 4 dias');
  });

  it('mostra o selo de férias só quando há data final', () => {
    expect(seloFerias({ ferias_fim: '2026-10-15' })).toBe('De férias até 15/10');
    expect(seloFerias({ ferias_fim: null })).toBe('');
  });
});
