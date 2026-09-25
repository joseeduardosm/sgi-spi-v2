import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { rotas } from './app.routes';
import { interceptadorAutenticacao } from './core/autenticacao/autenticacao.interceptor';
import { AutenticacaoService } from './core/autenticacao/autenticacao.service';

export const configuracaoAplicacao: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(rotas, withComponentInputBinding()),
    provideHttpClient(withInterceptors([interceptadorAutenticacao])),
    // Revalida no backend a sessão restaurada do navegador antes da primeira navegação
    provideAppInitializer(() => firstValueFrom(inject(AutenticacaoService).validarSessao())),
  ],
};
