// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar os utilitários de formatação da Reserva de Espaços.

import { dataBr, horaCurta, isoLocal } from './reservas.models';

describe('reservas.models', () => {
  it('formata data e hora sem mudar o dia', () => {
    expect(dataBr('2026-10-07')).toBe('07/10/2026');
    expect(horaCurta('09:30:00')).toBe('09:30');
    expect(isoLocal(new Date(2026, 9, 7, 23, 59))).toBe('2026-10-07');
  });
});
