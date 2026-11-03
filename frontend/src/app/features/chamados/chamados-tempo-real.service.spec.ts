// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a leitura das mensagens ao vivo (SSE) e os textos do painel de TV dos Chamados.

import { horaPainel, ItemPainel, tempoEspera, textoNivelPainel } from './chamados.models';
import { interpretar } from './chamados-tempo-real.service';

describe('Tempo real e painel dos Chamados', () => {
  it('lê o evento de chamado e ignora ping e outros tipos', () => {
    expect(interpretar('event: chamado\ndata: {"tipo": "novo", "numero": 12}')).toEqual({ tipo: 'novo', numero: 12 });
    expect(interpretar(': ping')).toBeNull();
    expect(interpretar('retry: 5000\n: conectado')).toBeNull();
    expect(interpretar('event: outro\ndata: {"numero": 1}')).toBeNull();
    expect(interpretar('event: chamado\ndata: quebrado')).toBeNull();
  });

  it('mostra o tempo de espera em minutos, horas ou dias', () => {
    const agora = Date.parse('2026-11-03T15:00:00Z');
    expect(tempoEspera('2026-11-03T14:26:00Z', agora)).toBe('34 min');
    expect(tempoEspera('2026-11-03T11:48:00Z', agora)).toBe('3h12');
    expect(tempoEspera('2026-11-02T14:00:00Z', agora)).toBe('1 dia');
    expect(tempoEspera('2026-11-04T14:00:00Z', agora)).toBe('0 min');
  });

  it('mostra a hora de hoje e a data de outro dia, no horário de São Paulo', () => {
    const agora = Date.parse('2026-11-03T15:00:00Z');
    expect(horaPainel('2026-11-03T13:58:00Z', agora)).toBe('10:58');
    expect(horaPainel('2026-11-01T13:58:00Z', agora)).toBe('01/11 10:58');
  });

  it('a situação sempre vem em texto, junto da cor', () => {
    const base = { nivel: 'atencao', percentual: 80, estourado: false, pausado: false } as ItemPainel;
    expect(textoNivelPainel(base)).toBe('80% do prazo');
    expect(textoNivelPainel({ ...base, estourado: true, nivel: 'perigo' })).toBe('Prazo estourado');
    expect(textoNivelPainel({ ...base, pausado: true })).toBe('Pendente');
    expect(textoNivelPainel({ ...base, nivel: 'resolvido' })).toBe('Resolvido');
    expect(textoNivelPainel({ ...base, nivel: 'sem', percentual: null })).toBe('Sem prazo');
  });
});
