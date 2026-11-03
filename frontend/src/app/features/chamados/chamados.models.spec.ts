// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar as regras de cor e texto dos prazos e do status dos Chamados.

import { nivelPrazo, PrazoSla, rotuloStatusSolicitante, textoPrazo } from './chamados.models';

const prazo = (p: Partial<PrazoSla>): PrazoSla => ({ vence_em: '2026-11-09T14:00:00Z', cumprido_em: null, estourado: false, percentual: 0, ...p });

describe('chamados.models', () => {
  it('pinta o prazo pela parte consumida: 50 âmbar, 75 laranja, 90 vermelho', () => {
    expect(nivelPrazo(prazo({ percentual: 49 }))).toBe('ok');
    expect(nivelPrazo(prazo({ percentual: 50 }))).toBe('alerta');
    expect(nivelPrazo(prazo({ percentual: 75 }))).toBe('atencao');
    expect(nivelPrazo(prazo({ percentual: 90 }))).toBe('perigo');
    expect(nivelPrazo(prazo({ estourado: true, percentual: 10 }))).toBe('perigo');
  });

  it('prazo cumprido fica verde (ou vermelho se foi com atraso) e sem SLA não tem cor', () => {
    expect(nivelPrazo(prazo({ cumprido_em: '2026-11-09T12:00:00Z' }))).toBe('cumprido');
    expect(nivelPrazo(prazo({ cumprido_em: '2026-11-09T15:00:00Z', estourado: true }))).toBe('perigo');
    expect(nivelPrazo(prazo({ vence_em: null }))).toBe('sem');
    expect(textoPrazo(prazo({ percentual: 62 }))).toBe('62% do prazo');
  });

  it('fala com o solicitante em linguagem simples', () => {
    expect(rotuloStatusSolicitante({ status_base: 'novo', setor_nome: 'Suporte TI', responsavel_nome: '' })).toBe('Aguardando Suporte TI');
    expect(rotuloStatusSolicitante({ status_base: 'em_atendimento', setor_nome: 'Suporte TI', responsavel_nome: 'João' })).toBe('Com João');
    expect(rotuloStatusSolicitante({ status_base: 'pendente', setor_nome: 'Suporte TI', responsavel_nome: 'João' })).toBe('Aguardando você');
    expect(rotuloStatusSolicitante({ status_base: 'solucionado', setor_nome: 'Suporte TI', responsavel_nome: 'João' })).toBe('Resolvido');
  });
});
