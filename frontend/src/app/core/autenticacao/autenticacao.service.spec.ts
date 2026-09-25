// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o serviço de autenticação, o interceptador e a guarda de login.
//
// Os testes usam HttpTestingController: nenhuma chamada real sai; cada teste diz qual resposta a
// "API" devolve com `flush`.

import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, provideRouter, Router, RouterStateSnapshot, UrlTree } from '@angular/router';

import { guardaAutenticacao } from './autenticacao.guards';
import { interceptadorAutenticacao } from './autenticacao.interceptor';
import { AutenticacaoService } from './autenticacao.service';

describe('AutenticacaoService', () => {
  let autenticacao: AutenticacaoService;
  let http: HttpTestingController;

  // Resposta de login falsa, com validade de `minutos`
  const respostaToken = (minutos: number) => ({
    token_acesso: 'jwt-teste',
    tipo_token: 'bearer',
    expira_em_segundos: minutos * 60,
    expira_em: new Date(Date.now() + minutos * 60_000).toISOString(),
    usuario: { id: 1, login: 'root', nome_completo: 'Administrador', papeis: ['SuperRoot'], origem: 'local' },
  });

  // Antes de cada teste: navegador limpo e serviços com o HTTP simulado
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: '**', children: [] }]),
        provideHttpClient(withInterceptors([interceptadorAutenticacao])),
        provideHttpClientTesting(),
      ],
    });
    autenticacao = TestBed.inject(AutenticacaoService);
    http = TestBed.inject(HttpTestingController);
  });

  // Depois de cada teste: garante que não sobrou nenhuma requisição sem resposta
  afterEach(() => http.verify());

  it('autentica, persiste a sessão e expõe o usuário', () => {
    autenticacao.entrar({ login: 'root', senha: 'x' }).subscribe();
    http.expectOne('/api/autenticacao/login').flush(respostaToken(60));

    expect(autenticacao.autenticado()).toBe(true);
    expect(autenticacao.usuario()?.login).toBe('root');
    expect(autenticacao.possuiPapel('SuperRoot')).toBe(true);
    expect(localStorage.getItem('contratos-spi.sessao')).toContain('jwt-teste');
  });

  it('envia o token nas chamadas da API e encerra a sessão em 401', () => {
    autenticacao.entrar({ login: 'root', senha: 'x' }).subscribe();
    const login = http.expectOne('/api/autenticacao/login');
    expect(login.request.headers.has('Authorization')).toBe(false);
    login.flush(respostaToken(60));

    // Qualquer chamada autenticada deve levar o token; um 401 encerra a sessão
    autenticacao.validarSessao().subscribe();
    const sessao = http.expectOne('/api/autenticacao/sessao');
    expect(sessao.request.headers.get('Authorization')).toBe('Bearer jwt-teste');
    sessao.flush({ detalhe: 'Sessão expirada.', codigo: 'nao_autenticado' }, { status: 401, statusText: 'Unauthorized' });

    expect(autenticacao.autenticado()).toBe(false);
    expect(localStorage.getItem('contratos-spi.sessao')).toBeNull();
  });

  it('sair limpa a sessão', () => {
    autenticacao.entrar({ login: 'root', senha: 'x' }).subscribe();
    http.expectOne('/api/autenticacao/login').flush(respostaToken(60));
    autenticacao.sair();
    expect(autenticacao.autenticado()).toBe(false);
  });

  it('guardaAutenticacao redireciona visitantes para /login com o destino', () => {
    const resultado = TestBed.runInInjectionContext(() =>
      guardaAutenticacao({} as ActivatedRouteSnapshot, { url: '/contratos' } as RouterStateSnapshot),
    );
    expect(resultado instanceof UrlTree).toBe(true);
    expect(TestBed.inject(Router).serializeUrl(resultado as UrlTree)).toBe('/login?retorno=%2Fcontratos');
  });
});
