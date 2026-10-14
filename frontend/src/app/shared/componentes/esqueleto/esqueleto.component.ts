// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar o esqueleto (skeleton) de uma tela ou bloco enquanto os dados carregam, com a forma do conteúdo final.

import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** Formas prontas: `texto` (parágrafo), `linha` (uma linha), `cartao`, `lista` (linhas com avatar), `tabela`, `painel` (cartões + gráfico), `quadro` (colunas de cartões, como o quadro de tarefas) e `formulario`. */
export type TipoEsqueleto = 'texto' | 'linha' | 'cartao' | 'lista' | 'tabela' | 'painel' | 'formulario' | 'quadro';

/**
 * Esqueleto de carregamento. Mantém a altura aproximada do conteúdo (sem salto de layout quando os dados chegam) e anuncia "Carregando" para leitor de tela.
 * O brilho (`.esq::after`) desliza por `transform` e fica estático com "reduzir movimento". Uso:
 * `@if (carregando()) { <app-esqueleto tipo="lista" [linhas]="6" /> } @else { ...conteúdo... }`.
 */
@Component({
  selector: 'app-esqueleto',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="esqueleto" [attr.data-tipo]="tipo()" role="status" aria-live="polite" aria-busy="true">
      <span class="somente-leitor">{{ rotulo() }}</span>
      @switch (tipo()) {
        @case ('linha') { <span class="esq linha"></span> }
        @case ('texto') { @for (n of itens(); track n) { <span class="esq linha" [style.width.%]="n === itens().length - 1 ? 60 : 100"></span> } }
        @case ('cartao') { <div class="esq cartao"></div> }
        @case ('lista') {
          @for (n of itens(); track n) { <div class="item-lista"><span class="esq avatar"></span><div><span class="esq linha" style="width: 55%"></span><span class="esq linha curta"></span></div></div> }
        }
        @case ('tabela') {
          <div class="tabela-esq">
            <div class="cab-tabela">@for (c of colunasLista(); track c) { <span class="esq linha"></span> }</div>
            @for (n of itens(); track n) { <div class="lin-tabela">@for (c of colunasLista(); track c) { <span class="esq linha"></span> }</div> }
          </div>
        }
        @case ('painel') {
          <div class="grade-cartoes">@for (n of [0, 1, 2, 3]; track n) { <div class="esq cartao baixo"></div> }</div>
          <div class="esq grafico"></div>
        }
        @case ('quadro') {
          <div class="quadro-esq">@for (c of colunasLista(); track c) { <div class="coluna-esq"><span class="esq linha curta"></span>@for (n of itens(); track n) { <div class="esq cartao baixo"></div> }</div> }</div>
        }
        @case ('formulario') {
          @for (n of itens(); track n) { <div class="campo-esq"><span class="esq linha curta"></span><span class="esq campo"></span></div> }
        }
      }
    </div>
  `,
  styleUrl: './esqueleto.component.scss',
})
export class EsqueletoComponent {
  readonly tipo = input<TipoEsqueleto>('lista');
  /** Quantidade de linhas, itens ou campos. */
  readonly linhas = input(5);
  readonly colunas = input(4);
  readonly rotulo = input('Carregando…');

  protected readonly itens = computed(() => Array.from({ length: this.linhas() }, (_, i) => i));
  protected readonly colunasLista = computed(() => Array.from({ length: this.colunas() }, (_, i) => i));
}
