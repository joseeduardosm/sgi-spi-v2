// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a trilha de navegação (breadcrumb) clicável no topo das páginas.

import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

/** Um passo da trilha; sem `rota`, o último passo aponta para a própria página e os demais ficam como texto. */
export interface ItemTrilha {
  rotulo: string;
  rota?: string | (string | number)[];
}

/**
 * Trilha "Início / Módulo / Página": cada passo leva à sua tela (Início → '/', módulo → tela do módulo,
 * página atual → a própria rota).
 */
@Component({
  selector: 'app-trilha',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p class="trilha" aria-label="Trilha de navegação">
      <a routerLink="/">Início</a>
      @for (item of passos(); track $index) {
        <span>/</span>
        @if (item.rota) { <a [routerLink]="item.rota" [attr.aria-current]="$last ? 'page' : null">{{ item.rotulo }}</a> }
        @else { {{ item.rotulo }} }
      }
    </p>
  `,
})
export class TrilhaComponent {
  readonly itens = input<ItemTrilha[]>([]);
  private readonly router = inject(Router);

  /** O último passo sem rota recebe a URL atual (sem a query string). */
  protected readonly passos = computed(() => {
    const itens = this.itens();
    return itens.map((item, i) => (item.rota || i < itens.length - 1 ? item : { ...item, rota: this.router.url.split('?')[0] }));
  });
}
