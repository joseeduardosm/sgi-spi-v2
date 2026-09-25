// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar as guardas de perfil pendente e de ACL.

import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, provideRouter, Router, RouterStateSnapshot, UrlTree } from '@angular/router';
import { firstValueFrom, isObservable, of } from 'rxjs';

import { AutenticacaoService } from '../autenticacao/autenticacao.service';
import { guardaAcl, guardaPerfil } from './acesso.guards';
import { AcessoService } from './acesso.service';

describe('guardas de perfil e ACL', () => {
  // Valores controlados pelos testes: perfil restrito e acesso concedido
  const restrito = signal(false);
  const concedido = signal(false);

  // Serviços reais substituídos por versões simuladas (`useValue`) que leem os signals acima
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: '**', children: [] }]),
        { provide: AutenticacaoService, useValue: { usuario: () => ({ perfil_restrito: restrito() }) } },
        { provide: AcessoService, useValue: { carregado: () => true, pode: () => concedido(), carregar: () => of(undefined) } },
      ],
    });
  });

  // Converte o resultado da guarda (UrlTree) em texto, para comparar
  const url = (r: unknown) => TestBed.inject(Router).serializeUrl(r as UrlTree);

  it('guardaPerfil redireciona para /perfil quando o perfil está pendente', () => {
    restrito.set(true);
    const r = TestBed.runInInjectionContext(() => guardaPerfil({} as ActivatedRouteSnapshot, { url: '/usuarios' } as RouterStateSnapshot));
    expect(url(r)).toBe('/perfil');
    const proprio = TestBed.runInInjectionContext(() => guardaPerfil({} as ActivatedRouteSnapshot, { url: '/perfil' } as RouterStateSnapshot));
    expect(proprio).toBe(true);
  });

  it('guardaAcl nega o módulo sem acesso efetivo', async () => {
    const rota = { data: { acl: 'usuarios' } } as unknown as ActivatedRouteSnapshot;
    concedido.set(false);
    let r = TestBed.runInInjectionContext(() => guardaAcl(rota, {} as RouterStateSnapshot));
    // A guarda pode devolver um Observable; nesse caso, espera o valor
    r = isObservable(r) ? await firstValueFrom(r) : r;
    expect(url(r)).toBe('/?acesso=negado');
    concedido.set(true);
    r = TestBed.runInInjectionContext(() => guardaAcl(rota, {} as RouterStateSnapshot));
    expect(isObservable(r) ? await firstValueFrom(r) : r).toBe(true);
  });
});
