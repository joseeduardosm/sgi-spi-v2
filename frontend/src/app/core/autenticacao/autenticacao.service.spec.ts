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

  const respostaToken = (minutos: number) => ({
    token_acesso: 'jwt-teste',
    tipo_token: 'bearer',
    expira_em_segundos: minutos * 60,
    expira_em: new Date(Date.now() + minutos * 60_000).toISOString(),
    usuario: { id: 1, login: 'root', nome_completo: 'Administrador', papeis: ['SuperRoot'], origem: 'local' },
  });

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
