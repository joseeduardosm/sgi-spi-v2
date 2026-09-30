// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho das telas de gestão de notícias (trilha, título e atalhos por papel).

import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { ItemTrilha, TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { NoticiasApiService } from '../noticias-api.service';
import { PapelNoticias } from '../noticias.models';

@Component({
  selector: 'app-cabecalho-noticias',
  imports: [RouterLink, RouterLinkActive, TrilhaComponent],
  template: `
    <div class="cabecalho-modulo">
      <div class="cabecalho-pagina" style="margin: 0">
        <div>
          <app-trilha [itens]="passos()" />
          <h1>{{ titulo() }}</h1>
          @if (descricao()) { <small>{{ descricao() }}</small> }
        </div>
      </div>
      <nav aria-label="Atalhos de notícias">
        <a class="acao-secundaria" routerLink="/noticias/gestao" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">
          Notícias @if (papel()?.aguardando_aprovacao) { <span class="contador-aba">{{ papel()!.aguardando_aprovacao }}</span> }
        </a>
        @if (papel()?.aprovador) { <a class="acao-secundaria" routerLink="/noticias/gestao/portal" routerLinkActive="ativo">Configurar portal</a> }
        <a class="acao-secundaria" routerLink="/" target="_blank">Ver portal ↗</a>
        @if (papel()?.redator) { <a class="acao-primaria" routerLink="/noticias/gestao/nova"><span>+</span> Nova notícia</a> }
      </nav>
    </div>
  `,
})
export class CabecalhoNoticiasComponent implements OnInit {
  readonly titulo = input.required<string>();
  readonly trilha = input<ItemTrilha[]>([]);
  readonly descricao = input('');
  private readonly api = inject(NoticiasApiService);
  protected readonly papel = signal<PapelNoticias | null>(null);
  protected readonly passos = computed<ItemTrilha[]>(() => [{ rotulo: 'Notícias', rota: '/noticias/gestao' }, ...this.trilha()]);

  ngOnInit(): void {
    this.api.papel().subscribe({ next: (p) => this.papel.set(p), error: () => undefined });
  }
}
