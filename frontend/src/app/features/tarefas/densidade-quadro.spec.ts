// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a escolha da densidade das colunas do quadro de tarefas.

import { escolherNivel, niveisPermitidos } from './densidade-quadro';

describe('densidade-quadro', () => {
  it('fica no cartão normal quando tudo cabe', () => {
    expect(escolherNivel(() => true, 400)).toBe(1);
  });

  it('sobe de nível só até caber', () => {
    expect(escolherNivel((n) => n >= 2, 400)).toBe(2);
    expect(escolherNivel((n) => n >= 3, 400)).toBe(3);
    expect(escolherNivel((n) => n >= 4, 400)).toBe(4);
  });

  it('se nada couber, fica no mais denso (rolagem como último recurso)', () => {
    expect(escolherNivel(() => false, 400)).toBe(4);
  });

  it('coluna estreita pula as subcolunas de cartão normal', () => {
    expect(niveisPermitidos(250)).toEqual([1, 4]);
    expect(escolherNivel((n) => n >= 2, 250)).toBe(4);
    expect(niveisPermitidos(330)).toEqual([1, 2, 3, 4]);
  });

  it('testa os níveis em ordem crescente', () => {
    const vistos: number[] = [];
    escolherNivel((n) => { vistos.push(n); return false; }, 500);
    expect(vistos).toEqual([1, 2, 3, 4]);
  });
});
