// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar os nomes dos níveis de acesso que vêm da API para cada módulo.

import { describe, expect, it } from 'vitest';

import { descricaoNivel, NiveisTextos, rotuloNivel } from './acesso.service';

const protocolo: NiveisTextos = {
  LEITURA: { rotulo: 'Consultar números', descricao: 'Vê a grade.' },
  MODIFICACAO: { rotulo: 'Reservar números de documentos', descricao: 'Reserva o próximo número.' },
  CONTROLE_TOTAL: { rotulo: 'Administrar o Protocolo', descricao: 'Cria tipos de documento.' },
};

describe('nomes dos níveis por módulo', () => {
  it('usa o texto que a API mandou para o módulo', () => {
    expect(rotuloNivel(protocolo, 'MODIFICACAO')).toBe('Reservar números de documentos');
    expect(descricaoNivel(protocolo, 'CONTROLE_TOTAL')).toBe('Cria tipos de documento.');
  });

  it('cai no nome genérico quando não há textos', () => {
    expect(rotuloNivel(undefined, 'MODIFICACAO')).toBe('Modificação');
    expect(rotuloNivel(undefined, 'CONTROLE_TOTAL')).toBe('Controle total');
    expect(descricaoNivel(undefined, 'LEITURA')).toBe('');
  });
});
