// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar os favoritos (conta + navegador) e os recentes (por usuário, últimas 5) do menu lateral.

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { AutenticacaoService } from '../autenticacao/autenticacao.service';
import { AtalhosService } from './atalhos.service';

describe('AtalhosService', () => {
  // Usuário logado simulado (um signal, para trocar de usuário e sair no meio do teste)
  const usuario = signal<{ id: number } | null>({ id: 1 });

  function preparar() {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AutenticacaoService, useValue: { usuario, autenticado: () => usuario() !== null } },
      ],
    });
    const atalhos = TestBed.inject(AtalhosService);
    const http = TestBed.inject(HttpTestingController);
    TestBed.tick();
    // Ao entrar, a lista de favoritos da conta é buscada
    http.match('/api/favoritos').forEach((r) => r.flush({ itens: [] }));
    return { atalhos, http };
  }

  beforeEach(() => {
    localStorage.clear();
    usuario.set({ id: 1 });
  });

  it('recentes: a tela mais nova vem primeiro, sem repetir, sempre só as últimas 5, ignorando "/" e o login', () => {
    const { atalhos } = preparar();
    for (let i = 1; i <= 10; i++) atalhos.registrar(`/tela${i}`, `Tela ${i}`);
    atalhos.registrar('/tela8', 'Tela 8');
    atalhos.registrar('/', 'Início');
    atalhos.registrar('/login', 'Login');
    const rotas = atalhos.recentes().map((r) => r.rota);
    expect(rotas).toEqual(['/tela8', '/tela10', '/tela9', '/tela7', '/tela6']);
    expect(JSON.parse(localStorage.getItem('sgi-spi.recentes.1')!)).toHaveLength(5);
  });

  it('recentes são por usuário: trocar de usuário mostra só os dele e sair esvazia', () => {
    const { atalhos } = preparar();
    atalhos.registrar('/contratos/1', 'Contrato 001/2026');
    usuario.set({ id: 2 });
    TestBed.tick();
    expect(atalhos.recentes()).toEqual([]);
    atalhos.registrar('/tarefas', 'Tarefas');
    usuario.set({ id: 1 });
    TestBed.tick();
    expect(atalhos.recentes().map((r) => r.rota)).toEqual(['/contratos/1']);
    usuario.set(null);
    TestBed.tick();
    expect(atalhos.recentes()).toEqual([]);
    atalhos.registrar('/ramais', 'Ramais');
    expect(atalhos.recentes()).toEqual([]);
  });

  it('remove as chaves antigas do navegador (que não eram por usuário)', () => {
    localStorage.setItem('sgi-spi.recentes', '[{"rota":"/x","rotulo":"X"}]');
    localStorage.setItem('sgi-spi.favoritos', '[{"rota":"/y","rotulo":"Y"}]');
    preparar();
    expect(localStorage.getItem('sgi-spi.recentes')).toBeNull();
    expect(localStorage.getItem('sgi-spi.favoritos')).toBeNull();
  });

  it('rotularAtual troca o nome da tela mais recente e do favorito dela', () => {
    const { atalhos } = preparar();
    atalhos.registrar('/contratos/1', 'Contrato');
    atalhos.alternar('/contratos/1', 'Contrato');
    atalhos.rotularAtual('Contrato 004/2025');
    expect(atalhos.recentes()[0].rotulo).toBe('Contrato 004/2025');
    expect(atalhos.favoritos()[0].rotulo).toBe('Contrato 004/2025');
  });

  it('favoritos: ficam no navegador (por usuário) e também são gravados na conta', () => {
    const { atalhos, http } = preparar();
    atalhos.alternar('/tarefas', 'Tarefas');
    expect(atalhos.ehFavorito('/tarefas')).toBe(true);
    expect(JSON.parse(localStorage.getItem('sgi-spi.favoritos.1')!)).toEqual([{ rota: '/tarefas', rotulo: 'Tarefas' }]);
    const put = http.expectOne((r) => r.method === 'PUT' && r.url === '/api/favoritos');
    expect(put.request.body).toEqual({ itens: [{ rota: '/tarefas', rotulo: 'Tarefas' }] });
    atalhos.alternar('/tarefas', 'Tarefas');
    expect(atalhos.ehFavorito('/tarefas')).toBe(false);
  });
});
