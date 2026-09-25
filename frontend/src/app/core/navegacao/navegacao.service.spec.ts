// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o filtro da barra lateral por papel, ACL e perfil pendente.

import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { AcessoService } from '../acesso/acesso.service';
import { AutenticacaoService } from '../autenticacao/autenticacao.service';
import { Papel, Usuario } from '../modelos/usuario.model';
import { NavegacaoService } from './navegacao.service';

describe('NavegacaoService', () => {
  // Usuário e acessos controlados pelos testes, lidos pelos serviços simulados
  const usuario = signal<Usuario | null>(null);
  const concedidos = signal<Set<string>>(new Set());
  const autenticacaoSimulada = {
    usuario,
    possuiPapel: (...papeis: Papel[]) => papeis.some((p) => usuario()?.papeis.includes(p) ?? false),
  };
  const acessoSimulado = { carregado: signal(true), pode: (slug: string) => concedidos().has(slug) };

  // Lista plana com os rótulos visíveis de todas as seções
  const rotulos = (nav: NavegacaoService) => nav.secoes().flatMap((s) => s.itens.map((i) => i.rotulo));

  beforeEach(() => {
    concedidos.set(new Set());
    TestBed.configureTestingModule({
      providers: [
        { provide: AutenticacaoService, useValue: autenticacaoSimulada },
        { provide: AcessoService, useValue: acessoSimulado },
      ],
    });
  });

  it('exibe a seção Administração apenas para o papel SuperRoot', () => {
    const nav = TestBed.inject(NavegacaoService);

    usuario.set({ id: 2, login: 'fulano', nome_completo: 'Fulano', papeis: [], origem: 'ldap' });
    expect(nav.secoes().map((s) => s.legenda)).toEqual(['Navegação']);

    usuario.set({ id: 1, login: 'root', nome_completo: 'Administrador', papeis: ['SuperRoot'], origem: 'local' });
    expect(nav.secoes().map((s) => s.legenda)).toEqual(['Navegação', 'Administração']);
  });

  it('oculta módulos sem acesso efetivo na ACL', () => {
    const nav = TestBed.inject(NavegacaoService);
    usuario.set({ id: 2, login: 'fulano', nome_completo: 'Fulano', papeis: [], origem: 'ldap' });
    expect(rotulos(nav)).not.toContain('Usuários');
    concedidos.set(new Set(['usuarios']));
    expect(rotulos(nav)).toContain('Usuários');
    expect(rotulos(nav)).not.toContain('Setores');
  });

  it('com o perfil pendente, mostra apenas "Meu perfil"', () => {
    const nav = TestBed.inject(NavegacaoService);
    usuario.set({ id: 2, login: 'fulano', nome_completo: 'Fulano', papeis: [], origem: 'ldap', perfil_restrito: true });
    expect(rotulos(nav)).toEqual(['Meu perfil']);
  });
});
