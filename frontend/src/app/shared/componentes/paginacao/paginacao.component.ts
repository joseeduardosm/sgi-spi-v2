// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir os controles de paginação das listas que vêm paginadas da API.

import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

/** Rodapé "Anterior · Página X de Y · Próxima" das listas paginadas no servidor. */
@Component({
  selector: 'app-paginacao',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (totalPaginas() > 1) {
      <nav class="paginacao-gestao" aria-label="Paginação">
        @if (total() !== null) { <span class="total">{{ total() }} registro(s)</span> }
        <button type="button" class="acao-secundaria" [disabled]="pagina() <= 1" (click)="mudar.emit(pagina() - 1)">Anterior</button>
        <span>Página {{ pagina() }} de {{ totalPaginas() }}</span>
        <button type="button" class="acao-secundaria" [disabled]="pagina() >= totalPaginas()" (click)="mudar.emit(pagina() + 1)">Próxima</button>
      </nav>
    }
  `,
  styles: `.total { margin-right: auto; }`,
})
export class PaginacaoComponent {
  // Página atual e tamanho da página (definidos pela tela que usa o componente)
  readonly pagina = input.required<number>();
  readonly tamanhoPagina = input.required<number>();
  /** Total de registros; nulo esconde o contador. */
  readonly total = input.required<number | null>();
  // Avisa a tela qual página foi pedida; a tela busca os dados na API
  readonly mudar = output<number>();

  // Quantidade de páginas (no mínimo 1), recalculada quando o total ou o tamanho mudam
  protected readonly totalPaginas = computed(() => Math.max(1, Math.ceil((this.total() ?? 0) / this.tamanhoPagina())));
}
