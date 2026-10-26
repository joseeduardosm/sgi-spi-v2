// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho comum das telas do Módulo RH (trilha, título e atalhos por papel).

import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { filter, map, startWith } from 'rxjs';
import { toSignal } from '@angular/core/rxjs-interop';

import { ItemTrilha, TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { grupoDaRota, gruposVisiveis } from './menu-rh';
import { RhApiService } from './rh-api.service';
import { PapeisRh } from './rh.models';

/** Cabeçalho do RH: "Voltar ao RH" (painel de entrada) e as telas irmãs do grupo da página atual, numeradas nas sequências reais (ver `menu-rh.ts`). */
@Component({
  selector: 'app-cabecalho-rh',
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
      <nav aria-label="Telas do Módulo RH">
        <a class="acao-secundaria" routerLink="/rh">← Voltar ao RH</a>
        @if (grupo(); as g) {
          <span class="rh-subnav-grupo">{{ g.titulo }}</span>
          @for (t of g.telas; track t.rota; let i = $index) {
            <a class="acao-secundaria" [routerLink]="t.rota" routerLinkActive="ativo" ariaCurrentWhenActive="page">@if (g.numerado) { <b>{{ i + 1 }}</b> }{{ t.rotulo }}</a>
          }
        }
      </nav>
    </div>
  `,
})
export class CabecalhoRhComponent implements OnInit {
  readonly titulo = input.required<string>();
  readonly trilha = input<string[]>([]);
  readonly descricao = input('');
  private readonly api = inject(RhApiService);
  private readonly roteador = inject(Router);
  private readonly url = toSignal(this.roteador.events.pipe(filter((e) => e instanceof NavigationEnd), map(() => this.roteador.url), startWith(this.roteador.url)), { initialValue: this.roteador.url });
  protected readonly papeis = signal<PapeisRh | null>(null);
  /** Grupo da página atual, só com as telas que a pessoa vê (fora dos grupos, como o histórico, sobra só o "Voltar ao RH"). */
  protected readonly grupo = computed(() => {
    const atual = grupoDaRota(this.url());
    const p = this.papeis();
    return atual && p ? gruposVisiveis(p).find((g) => g.id === atual.id) : undefined;
  });
  /** "Início / RH / Página": RH leva ao painel de entrada; a página, a ela mesma. */
  protected readonly passos = computed<ItemTrilha[]>(() => [{ rotulo: 'RH', rota: '/rh' }, ...this.trilha().map((rotulo) => ({ rotulo }))]);

  ngOnInit(): void {
    this.api.papeis().subscribe({ next: (p) => this.papeis.set(p), error: () => undefined });
  }
}
