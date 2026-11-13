/**
 * =============================================================================
 * ARQUIVO: tarefas.recorrencia.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testar a regra padrão das tarefas recorrentes.
 *
 * RESUMO TÉCNICO:
 * Chama regraPadrao(2) e confere o objeto completo da regra e o rótulo curto
 * do dia (índice 2 = "Qua", porque a semana começa na segunda = 0).
 *
 * FINALIDADE DE NEGÓCIO:
 * Garante que, ao marcar "Repetir esta tarefa", a rotina nasça semanal, no
 * dia do prazo, sem término e sem antecedência, que é o comportamento
 * esperado por quem cria a recorrência.
 *
 * CONTEXTO NO SISTEMA:
 * Testa regraPadrao e DIAS_SEMANA_CURTOS de tarefas.models.ts, usados pelo
 * seletor-recorrencia.component.ts. Roda com o Vitest via "npx ng test".
 *
 * =============================================================================
 */

import { DIAS_SEMANA_CURTOS, regraPadrao } from './tarefas.models';

describe('tarefas recorrentes', () => {
  it('a regra padrão é semanal, no dia pedido, sem término', () => {
    const regra = regraPadrao(2);
    expect(regra).toEqual({ frequencia: 'semanal', intervalo: 1, dias_semana: [2], somente_dias_uteis: false, antecedencia_dias: 0, fim: null, max_ocorrencias: null });
    expect(DIAS_SEMANA_CURTOS[regra.dias_semana[0]]).toBe('Qua');
  });
});
