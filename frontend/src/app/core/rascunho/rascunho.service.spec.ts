// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o serviço de rascunhos de formulários guardados no navegador.

import { DestroyRef, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AutenticacaoService } from '../autenticacao/autenticacao.service';
import { RascunhoService } from './rascunho.service';

describe('RascunhoService', () => {
  const usuario = signal<{ id: number } | null>({ id: 7 });
  let servico: RascunhoService;
  let destruir: { onDestroy: (f: () => void) => void; correr: () => void };

  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [{ provide: AutenticacaoService, useValue: { usuario } }] });
    servico = TestBed.inject(RascunhoService);
    let aoDestruir: () => void = () => undefined;
    destruir = { onDestroy: (f) => (aoDestruir = f), correr: () => aoDestruir() };
  });

  afterEach(() => vi.useRealTimers());

  it('grava ao mudar, lê de volta e apaga quando o formulário esvazia', () => {
    let estado: { texto: string } | null = { texto: 'olá' };
    servico.vigiar(destruir as unknown as DestroyRef, 'diario:1', () => estado);
    vi.advanceTimersByTime(2100);
    expect(servico.ler<{ texto: string }>('diario:1')?.dados).toEqual({ texto: 'olá' });
    estado = null;
    vi.advanceTimersByTime(2100);
    expect(servico.ler('diario:1')).toBeNull();
  });

  it('o rascunho é de cada usuário', () => {
    servico.vigiar(destruir as unknown as DestroyRef, 'x', () => ({ a: 1 }));
    vi.advanceTimersByTime(2100);
    usuario.set({ id: 8 });
    expect(servico.ler('x')).toBeNull();
    usuario.set({ id: 7 });
    expect(servico.ler('x')).not.toBeNull();
  });

  it('descarta rascunho com mais de 7 dias e para de vigiar ao destruir', () => {
    localStorage.setItem('sgi-spi.rascunho.7.velho', JSON.stringify({ dados: 1, salvoEm: new Date(Date.now() - 8 * 86400000).toISOString() }));
    expect(servico.ler('velho')).toBeNull();
    expect(localStorage.getItem('sgi-spi.rascunho.7.velho')).toBeNull();
    let chamadas = 0;
    servico.vigiar(destruir as unknown as DestroyRef, 'y', () => ({ n: ++chamadas }));
    destruir.correr();
    vi.advanceTimersByTime(10000);
    expect(chamadas).toBe(0);
  });
});
