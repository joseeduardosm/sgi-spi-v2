// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a regra padrão das tarefas recorrentes.

import { DIAS_SEMANA_CURTOS, regraPadrao } from './tarefas.models';

describe('tarefas recorrentes', () => {
  it('a regra padrão é semanal, no dia pedido, sem término', () => {
    const regra = regraPadrao(2);
    expect(regra).toEqual({ frequencia: 'semanal', intervalo: 1, dias_semana: [2], somente_dias_uteis: false, antecedencia_dias: 0, fim: null, max_ocorrencias: null });
    expect(DIAS_SEMANA_CURTOS[regra.dias_semana[0]]).toBe('Qua');
  });
});
