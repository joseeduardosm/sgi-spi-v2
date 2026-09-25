// Criado por José Eduardo Santana Martins
// Este arquivo serve para registrar os serviços globais da aplicação (rotas, HTTP e inicialização da sessão).

import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { rotas } from './app.routes';
import { interceptadorAutenticacao } from './core/autenticacao/autenticacao.interceptor';
import { AutenticacaoService } from './core/autenticacao/autenticacao.service';

/** Configuração global usada em `main.ts` ao iniciar a aplicação. */
export const configuracaoAplicacao: ApplicationConfig = {
  providers: [
    // Mostra no console erros não tratados do navegador
    provideBrowserGlobalErrorListeners(),
    // Rotas; `withComponentInputBinding` entrega parâmetros da URL direto nos `input()` dos componentes
    provideRouter(rotas, withComponentInputBinding()),
    // HttpClient com o interceptador que anexa o token JWT e trata a sessão expirada
    provideHttpClient(withInterceptors([interceptadorAutenticacao])),
    // Revalida no backend a sessão restaurada do navegador antes da primeira navegação
    provideAppInitializer(() => firstValueFrom(inject(AutenticacaoService).validarSessao())),
  ],
};
