// Criado por José Eduardo Santana Martins
// Este arquivo serve para registrar os serviços globais da aplicação (rotas, HTTP e inicialização da sessão).

import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, inject, isDevMode, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideServiceWorker } from '@angular/service-worker';
import { ActivatedRouteSnapshot, provideRouter, withComponentInputBinding, withPreloading, withViewTransitions } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { rotas } from './app.routes';
import { interceptadorAutenticacao } from './core/autenticacao/autenticacao.interceptor';
import { PrecarregamentoOcioso } from './core/navegacao/precarregamento';
import { interceptadorProgresso } from './core/progresso/progresso.interceptor';
import { AutenticacaoService } from './core/autenticacao/autenticacao.service';

/** Configuração global usada em `main.ts` ao iniciar a aplicação. */
export const configuracaoAplicacao: ApplicationConfig = {
  providers: [
    // Mostra no console erros não tratados do navegador
    provideBrowserGlobalErrorListeners(),
    // Rotas; `withComponentInputBinding` entrega parâmetros da URL direto nos `input()` dos componentes
    provideRouter(
      rotas,
      withComponentInputBinding(),
      withPreloading(PrecarregamentoOcioso),
      // Troca de tela com fade + deslize curto (View Transitions). Mudar só filtro, aba ou busca na mesma tela (query string) não anima: é ação frequente.
      withViewTransitions({
        skipInitialTransition: true,
        onViewTransitionCreated: ({ transition, from, to }) => {
          if (caminhoDaRota(from) === caminhoDaRota(to)) transition.skipTransition();
        },
      }),
    ),
    // HttpClient com o interceptador que anexa o token JWT e trata a sessão expirada
    provideHttpClient(withInterceptors([interceptadorAutenticacao, interceptadorProgresso])),
    // Revalida no backend a sessão restaurada do navegador antes da primeira navegação
    provideAppInitializer(() => firstValueFrom(inject(AutenticacaoService).validarSessao())),
    // Service worker só do Patrimônio (uso no celular com sinal fraco): o escopo limita o cache às telas de /patrimonio
    provideServiceWorker('ngsw-worker.js', { enabled: !isDevMode(), scope: '/patrimonio/', registrationStrategy: 'registerWhenStable:30000' }),
  ],
};

/** Caminho da rota sem a query string (para saber se mudou de tela ou só de filtro). */
function caminhoDaRota(rota: ActivatedRouteSnapshot): string {
  return rota.pathFromRoot.map((r) => r.url.map((s) => s.path).join('/')).join('/');
}
