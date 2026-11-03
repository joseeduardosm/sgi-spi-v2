// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar a minissérie (sparkline) que fica no rodapé dos cartões de indicador: a tendência do número ao longo do período.

import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/**
 * Linha fina com área suave, sem eixos nem números: só a tendência (o número de verdade está no cartão).
 * `null` na série vira o valor anterior (semana sem dado não derruba a linha). A cor vem do tom do cartão, pelos tokens do tema.
 */
@Component({
  selector: 'app-minigrafico',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (caminho(); as c) {
      <svg viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true" [attr.data-tom]="tom()">
        <path class="area" [attr.d]="c.area" />
        <path class="linha" [attr.d]="c.linha" vector-effect="non-scaling-stroke" />
      </svg>
    }
  `,
  styles: `
    :host { display: block; height: 28px; }
    svg { display: block; width: 100%; height: 100%; color: var(--spi-apagado); overflow: visible; }
    svg[data-tom='info'] { color: var(--spi-info); }
    svg[data-tom='sucesso'] { color: var(--spi-sucesso); }
    svg[data-tom='alerta'] { color: var(--spi-alerta); }
    svg[data-tom='perigo'] { color: var(--spi-perigo); }
    .linha { fill: none; stroke: currentColor; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
    .area { fill: currentColor; opacity: 0.12; }
  `,
})
export class MinigraficoComponent {
  readonly dados = input.required<(number | null)[]>();
  readonly tom = input<'info' | 'sucesso' | 'alerta' | 'perigo' | 'neutro'>('neutro');

  /** Pontos espalhados na largura (0–100) e na altura (2–22, para a linha não encostar na borda). Menos de 2 pontos: nada a desenhar. */
  protected readonly caminho = computed(() => {
    let anterior = 0;
    const valores = this.dados().map((v) => (anterior = v ?? anterior));
    if (valores.length < 2) return null;
    const maior = Math.max(...valores), menor = Math.min(...valores);
    const faixa = maior - menor || 1;
    const pontos = valores.map((v, i) => [(i * 100) / (valores.length - 1), 22 - ((v - menor) / faixa) * 20]);
    const linha = pontos.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
    return { linha, area: `${linha} L100,24 L0,24 Z` };
  });
}
