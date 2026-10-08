// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a paleta e os utilitários dos marcadores das tarefas.

import { classeMarcador, PALETA_MARCADORES, semAcento } from './marcadores.paleta';

describe('marcadores.paleta', () => {
  it('tem 12 cores e usa a classe do índice (ou a cor 1 quando inválido)', () => {
    expect(PALETA_MARCADORES.length).toBe(12);
    expect(classeMarcador(4)).toBe('marcador-tarefa marcador-cor-4');
    expect(classeMarcador(99)).toBe('marcador-tarefa marcador-cor-1');
    expect(classeMarcador(undefined)).toBe('marcador-tarefa marcador-cor-1');
  });

  it('filtra sem acentos nem maiúsculas', () => {
    expect(semAcento('Jurídico')).toBe('juridico');
  });
});
