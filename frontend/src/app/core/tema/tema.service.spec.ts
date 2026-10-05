// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o tema da interface (aplicação no <html>, armazenamento e gravação na conta).

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { AutenticacaoService } from '../autenticacao/autenticacao.service';
import { aplicarTema, CHAVE_TEMA, TemaService } from './tema.service';

describe('TemaService', () => {
  beforeEach(() => {
    localStorage.removeItem(CHAVE_TEMA);
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
  });

  it('aplica o tema no <html> (sistema claro ou escuro no modo automático)', () => {
    aplicarTema('escuro', false);
    expect(document.documentElement.getAttribute('data-tema')).toBe('escuro');
    expect(document.documentElement.getAttribute('data-bs-theme')).toBe('dark');
    aplicarTema('claro', true);
    expect(document.documentElement.getAttribute('data-tema')).toBe('claro');
    aplicarTema('auto', true);
    expect(document.documentElement.getAttribute('data-tema')).toBe('escuro');
  });

  it('sem sessão, a escolha fica só no navegador', () => {
    const tema = TestBed.inject(TemaService);
    tema.escolher('escuro');
    expect(localStorage.getItem(CHAVE_TEMA)).toBe('escuro');
    expect(tema.preferencia()).toBe('escuro');
    TestBed.inject(HttpTestingController).verify();
  });

  it('com sessão, grava também na conta', () => {
    const usuario = { id: 1, login: 'fulano', nome_completo: 'Fulano', papeis: [], origem: 'local', tema: 'auto' };
    const definirUsuario = vi.fn();
    TestBed.overrideProvider(AutenticacaoService, { useValue: { usuario: () => usuario, definirUsuario } });
    const tema = TestBed.inject(TemaService);
    tema.escolher('escuro');
    const requisicao = TestBed.inject(HttpTestingController).expectOne('/api/autenticacao/tema');
    expect(requisicao.request.method).toBe('PUT');
    expect(requisicao.request.body).toEqual({ tema: 'escuro' });
    requisicao.flush({ ...usuario, tema: 'escuro' });
    expect(definirUsuario).toHaveBeenCalledWith({ ...usuario, tema: 'escuro' });
  });
});
