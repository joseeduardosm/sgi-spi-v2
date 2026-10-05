// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a busca global: agrupamento, telas do menu e abertura do resultado.

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';

import { NavegacaoService } from '../../../core/navegacao/navegacao.service';
import { BuscaGlobalComponent, normalizar } from './busca-global.component';

describe('BuscaGlobalComponent', () => {
  const navegacao = { secoes: () => [{ legenda: 'Navegação', itens: [{ id: 'm', rotulo: 'Módulos', filhos: [{ id: 'ramais', rotulo: 'Ramais', rota: '/ramais' }] }] }] };

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), { provide: NavegacaoService, useValue: navegacao }] });
  });
  afterEach(() => vi.useRealTimers());

  it('normaliza acentos e maiúsculas', () => {
    expect(normalizar('  Contratações ')).toBe('contratacoes');
  });

  it('mostra telas do menu na hora e resultados da API agrupados; Enter abre o primeiro', () => {
    const fixture = TestBed.createComponent(BuscaGlobalComponent);
    const http = TestBed.inject(HttpTestingController);
    const roteador = TestBed.inject(Router);
    const abrir = vi.spyOn(roteador, 'navigateByUrl').mockResolvedValue(true);
    fixture.detectChanges();
    const campo = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    campo.value = 'ram';
    campo.dispatchEvent(new Event('input'));
    vi.advanceTimersByTime(300);
    http.expectOne((r) => r.url === '/api/busca' && r.params.get('q') === 'ram').flush({
      itens: [{ tipo: 'pessoa', id: '7', titulo: 'Maria Ramos', subtitulo: 'ramal 8123', rota: '/ramais?q=Maria%20Ramos' }],
    });
    fixture.detectChanges();
    const texto = fixture.nativeElement.textContent as string;
    expect(texto).toContain('Telas');
    expect(texto).toContain('Ramais');
    expect(texto).toContain('Pessoas');
    expect(texto).toContain('Maria Ramos');
    campo.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(abrir).toHaveBeenCalledWith('/ramais');
  });
});
