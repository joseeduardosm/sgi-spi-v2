// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar um feixe de luz que percorre a borda de um cartão (adaptação do "Border Beam" do MagicUI).

import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Feixe animado na borda do elemento pai (que precisa de `position: relative`). Decorativo e desligado com movimento reduzido. */
@Component({
  selector: 'app-feixe-borda',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    'aria-hidden': 'true',
    '[style.--feixe-tamanho.px]': 'tamanho()',
    '[style.--feixe-duracao.s]': 'duracao()',
    '[style.--feixe-atraso.s]': '-atraso()',
    '[style.--feixe-borda.px]': 'larguraBorda()',
    '[style.--feixe-de]': 'corInicial()',
    '[style.--feixe-ate]': 'corFinal()',
    '[style.--feixe-sentido]': "inverso() ? 'reverse' : 'normal'",
    '[style.--feixe-inicio.%]': 'deslocamentoInicial()',
  },
  template: '<span class="feixe"></span>',
  styles: `
    :host {
      position: absolute;
      inset: 0;
      border-radius: inherit;
      pointer-events: none;
      border: var(--feixe-borda, 1px) solid transparent;
      /* Máscara: só a faixa da borda fica visível */
      mask: linear-gradient(transparent, transparent), linear-gradient(#000, #000);
      mask-clip: padding-box, border-box;
      mask-composite: intersect;
      -webkit-mask: linear-gradient(transparent, transparent), linear-gradient(#000, #000);
      -webkit-mask-clip: padding-box, border-box;
      -webkit-mask-composite: source-in;
    }
    .feixe {
      position: absolute;
      aspect-ratio: 1;
      width: var(--feixe-tamanho, 50px);
      background: linear-gradient(to left, var(--feixe-de, #ffaa40), var(--feixe-ate, #9c40ff), transparent);
      offset-anchor: 90% 50%;
      offset-path: rect(0 auto auto 0 round var(--feixe-tamanho, 50px));
      animation: percorrer-borda var(--feixe-duracao, 6s) linear var(--feixe-atraso, 0s) infinite var(--feixe-sentido, normal);
    }
    @keyframes percorrer-borda {
      from { offset-distance: var(--feixe-inicio, 0%); }
      to { offset-distance: calc(100% + var(--feixe-inicio, 0%)); }
    }
    @media (prefers-reduced-motion: reduce) {
      .feixe { animation: none; display: none; }
    }
  `,
})
export class FeixeBordaComponent {
  readonly tamanho = input(50);
  readonly duracao = input(6);
  readonly atraso = input(0);
  readonly corInicial = input('#ffaa40');
  readonly corFinal = input('#9c40ff');
  readonly larguraBorda = input(1);
  readonly inverso = input(false);
  readonly deslocamentoInicial = input(0);
}
