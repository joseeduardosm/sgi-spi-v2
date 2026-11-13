/**
 * =============================================================================
 * ARQUIVO: marcadores-competencia.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testar os marcadores (chips) da competência atual mostrados na carteira de
 * contratos.
 *
 * RESUMO TÉCNICO:
 * Testes unitários puros (Jasmine) da função marcadoresCompetencia: contrato
 * sem competências, tudo concluído, competência disponível e atrasada, e
 * várias competências em andamento (uma linha por competência, etapas abertas
 * unidas por " + "). Confere textos e a rota para a execução.
 *
 * FINALIDADE DE NEGÓCIO:
 * Protege o resumo que o gestor vê na carteira: em que mês (competência) cada
 * contrato está, qual etapa está aberta e se está atrasado, além do atalho
 * direto para a execução daquele mês.
 *
 * CONTEXTO NO SISTEMA:
 * Testa marcadores-competencia.ts, usado por carteira.component. Os rótulos
 * das etapas vêm de compartilhado/rotulos.ts.
 *
 * =============================================================================
 */

import { marcadoresCompetencia } from './marcadores-competencia';

// Contrato mínimo usado em todos os casos: só os campos que a função lê.
const base = { id: 'c1', sem_competencias: false };

describe('marcadoresCompetencia', () => {
  it('sem execução gerada', () => {
    expect(marcadoresCompetencia({ ...base, sem_competencias: true, competencia_atual: null }).flat().map((m) => m.texto)).toEqual(['Sem competências']);
  });

  it('tudo concluído', () => {
    expect(marcadoresCompetencia({ ...base, competencia_atual: null }).flat().map((m) => m.texto)).toEqual(['Em dia']);
  });

  it('competência disponível e atrasada (sem nenhuma iniciada)', () => {
    const m = marcadoresCompetencia({ ...base, competencia_atual: { identificador: '2026-01', rotulo: '01/2026', situacao: 'disponivel', etapas: ['medicao'], atrasada: true } });
    expect(m.length).toBe(1);
    expect(m[0].map((x) => x.texto)).toEqual(['01/2026', 'Medição · Disponível', 'Atrasada']);
    expect(m[0][0].rota).toEqual(['/contratos', 'c1', 'execucao', '2026-01']);
  });

  // Competência = o mês de referência da execução do contrato (medição, nota fiscal, pagamento...).
  it('uma linha por competência em andamento, com as etapas abertas juntas', () => {
    const andamento = [
      { identificador: '2026-08', rotulo: '08/2026', situacao: 'em_andamento' as const, etapas: ['cadin'], atrasada: false },
      { identificador: '2026-09', rotulo: '09/2026', situacao: 'em_andamento' as const, etapas: ['retencao', 'checklist'], atrasada: true },
    ];
    const m = marcadoresCompetencia({ ...base, competencia_atual: andamento[0], competencias_em_andamento: andamento });
    expect(m.length).toBe(2);
    expect(m[0].map((x) => x.texto)).toEqual(['08/2026 · CADIN']);
    expect(m[1].map((x) => x.texto)).toEqual(['09/2026 · Retenção de tributos + Checklist', 'Atrasada']);
  });
});
