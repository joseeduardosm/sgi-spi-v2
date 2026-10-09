// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar os marcadores da competência atual na carteira.

import { marcadoresCompetencia } from './marcadores-competencia';

const base = { id: 'c1', sem_competencias: false };

describe('marcadoresCompetencia', () => {
  it('sem execução gerada', () => {
    expect(marcadoresCompetencia({ ...base, sem_competencias: true, competencia_atual: null }).map((m) => m.texto)).toEqual(['Sem competências']);
  });

  it('tudo concluído', () => {
    expect(marcadoresCompetencia({ ...base, competencia_atual: null }).map((m) => m.texto)).toEqual(['Em dia']);
  });

  it('competência disponível e atrasada', () => {
    const m = marcadoresCompetencia({ ...base, competencia_atual: { identificador: '2026-01', rotulo: '01/2026', situacao: 'disponivel', etapas: ['medicao'], atrasada: true } });
    expect(m.map((x) => x.texto)).toEqual(['01/2026', 'Medição · Disponível', 'Atrasada']);
    expect(m[0].rota).toEqual(['/contratos', 'c1', 'execucao', '2026-01']);
  });

  it('três etapas abertas depois da nota fiscal', () => {
    const m = marcadoresCompetencia({ ...base, competencia_atual: { identificador: '2026-02', rotulo: '02/2026', situacao: 'em_andamento', etapas: ['retencao', 'cadin', 'checklist'], atrasada: false } });
    expect(m.length).toBe(4);
    expect(m.slice(1).every((x) => x.cor === 7)).toBe(true);
  });
});
