// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar a moldura do portal de notícias para visitantes (sem login): cabeçalho institucional com "Entrar".

import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

/**
 * Portal público (página inicial para quem não entrou no sistema). Quem está logado vê as mesmas telas dentro do
 * layout autenticado, com a barra lateral; a escolha é feita nas rotas (`canMatch`).
 */
@Component({
  selector: 'app-layout-portal',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <a class="link-pular-portal" href="#conteudo-portal">Pular para o conteúdo</a>
    <div class="pagina-portal">
      <header class="topo-portal">
        <div class="largura-portal-noticias topo-portal-interno">
          <a class="marca-portal" routerLink="/" aria-label="Início do portal">
            <img class="logo-portal" src="assets/imagens/4-vertical-slogan.png" alt="Governo do Estado de São Paulo" />
            <span class="filete-portal" aria-hidden="true"></span>
            <span class="nome-portal"><strong>SECRETARIA DE PARCERIAS<br />EM INVESTIMENTOS</strong></span>
          </a>
          <nav class="nav-portal" aria-label="Portal">
            <a routerLink="/" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">Início</a>
            <a routerLink="/noticias" routerLinkActive="ativo">Notícias</a>
            <button type="button" class="acao-primaria" (click)="entrar()">Entrar no SGI SPI</button>
          </nav>
        </div>
      </header>
      <main id="conteudo-portal" class="largura-portal-noticias conteudo-portal" tabindex="-1">
        <router-outlet />
      </main>
      <footer class="rodape-portal">Governo do Estado de São Paulo · Secretaria de Parcerias em Investimentos</footer>
    </div>
  `,
})
export class LayoutPortalComponent {
  private readonly roteador = inject(Router);

  /** Vai ao login e, depois dele, volta para a página em que a pessoa estava. */
  protected entrar(): void {
    const atual = this.roteador.url.split('#')[0];
    void this.roteador.navigate(['/login'], { queryParams: atual && atual !== '/' ? { retorno: atual } : {} });
  }
}
