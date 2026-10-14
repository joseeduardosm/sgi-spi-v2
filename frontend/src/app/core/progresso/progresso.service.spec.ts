// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a barra de progresso: atraso para não piscar, tempo mínimo visível e contagem de requisições.

import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ATRASO_MS, MINIMO_VISIVEL_MS, ProgressoService } from './progresso.service';

describe('ProgressoService', () => {
  let servico: ProgressoService;

  beforeEach(() => {
    vi.useFakeTimers();
    servico = TestBed.inject(ProgressoService);
  });
  afterEach(() => vi.useRealTimers());

  it('não pisca com resposta rápida', () => {
    servico.iniciarRequisicao();
    vi.advanceTimersByTime(ATRASO_MS - 10);
    servico.terminarRequisicao();
    vi.advanceTimersByTime(1000);
    expect(servico.visivel()).toBe(false);
  });

  it('aparece depois do atraso e fica pelo menos o tempo mínimo', () => {
    servico.iniciarRequisicao();
    vi.advanceTimersByTime(ATRASO_MS + 1);
    expect(servico.visivel()).toBe(true);
    servico.terminarRequisicao();
    vi.advanceTimersByTime(MINIMO_VISIVEL_MS - 50);
    expect(servico.visivel()).toBe(true);
    vi.advanceTimersByTime(100);
    expect(servico.visivel()).toBe(false);
  });

  it('só some quando todas as requisições terminam', () => {
    servico.iniciarRequisicao();
    servico.iniciarRequisicao();
    vi.advanceTimersByTime(ATRASO_MS + 1);
    servico.terminarRequisicao();
    vi.advanceTimersByTime(MINIMO_VISIVEL_MS + 50);
    expect(servico.visivel()).toBe(true);
    servico.terminarRequisicao();
    vi.advanceTimersByTime(MINIMO_VISIVEL_MS + 50);
    expect(servico.visivel()).toBe(false);
  });
});

describe('ProgressoService: envio de arquivo', () => {
  it('calcula o percentual do envio e volta a indeterminado ao terminar', () => {
    const servico = TestBed.inject(ProgressoService);
    expect(servico.envio()).toBeNull();
    servico.informarEnvio(250, 1000);
    expect(servico.envio()).toBe(25);
    servico.informarEnvio(2000, 1000);
    expect(servico.envio()).toBe(100);
    servico.informarEnvio(null);
    expect(servico.envio()).toBeNull();
  });
});
