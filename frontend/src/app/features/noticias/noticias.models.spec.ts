// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar os utilitários do Módulo Notícias (datas do formulário, srcset da capa e tamanho).

import { deCampo, paraCampo, srcsetCapa, tamanhoLegivel } from './noticias.models';

describe('utilitários de notícias', () => {
  it('converte datas entre o campo e o ISO', () => {
    const iso = new Date(2026, 8, 30, 14, 5).toISOString();
    expect(paraCampo(iso)).toBe('2026-09-30T14:05');
    expect(deCampo('2026-09-30T14:05')).toBe(iso);
    expect(deCampo('')).toBeNull();
    expect(paraCampo(null)).toBe('');
  });

  it('monta o srcset e o tamanho legível', () => {
    expect(srcsetCapa({ '400': '/a', '800': '/b' })).toBe('/a 400w, /b 800w');
    expect(tamanhoLegivel(627 * 1024)).toBe('627 KB');
  });
});
