// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar os utilitários de texto do Módulo Tarefas (prazo relativo, duração e tamanho).

import { duracao, prazoRelativo, tamanhoLegivel } from './tarefas.models';

describe('utilitários de tarefas', () => {
  it('descreve o prazo relativo', () => {
    const dia = 86_400_000;
    expect(prazoRelativo(new Date(Date.now() - 3 * dia - 1000).toISOString())).toBe('Atrasada há 3 dias');
    expect(prazoRelativo(new Date(Date.now() + 5 * dia - 1000).toISOString())).toBe('Vence em 5 dias');
    expect(prazoRelativo(new Date(Date.now() - dia).toISOString(), true)).toBe('');
  });

  it('formata duração e tamanho', () => {
    expect(duracao(3 * 3600 + 20 * 60)).toBe('3 h 20 min');
    expect(duracao(2 * 86400 + 4 * 3600)).toBe('2 d 4 h');
    expect(tamanhoLegivel(25)).toBe('25 B');
    expect(tamanhoLegivel(1.2 * 1024 * 1024)).toBe('1,2 MB');
  });
});
