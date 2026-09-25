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
  readonly pagina = input.required<number>();
  readonly tamanhoPagina = input.required<number>();
  /** Total de registros; nulo esconde o contador. */
  readonly total = input.required<number | null>();
  readonly mudar = output<number>();

  protected readonly totalPaginas = computed(() => Math.max(1, Math.ceil((this.total() ?? 0) / this.tamanhoPagina())));
}
