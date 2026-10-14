// Criado por José Eduardo Santana Martins
// Este arquivo serve para escolher uma cor entre bolinhas (releitura do Color Selector do Spell): a escolhida ganha um anel.

import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

export interface CorSelecionavel {
  /** Cor da bolinha. */
  cor: string;
  /** Nome para leitores de tela. */
  rotulo: string;
}

/** Grupo de bolinhas de cor; a escolhida tem um anel (vazio por dentro, na cor do fundo) e as demais encolhem ao clique. */
@Component({
  selector: 'app-seletor-cor',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="bolinhas" [class.em-grade]="colunas() > 0" [style.--colunas]="colunas()" role="radiogroup" [attr.aria-label]="rotulo()">
      @for (c of cores(); track $index; let i = $index) {
        <button type="button" role="radio" class="bolinha" [class.pequeno]="tamanho() === 'pequeno'" [class.grande]="tamanho() === 'grande'"
                [class.escolhida]="i === valor()" [style.--cor]="c.cor" [attr.aria-checked]="i === valor()" [attr.aria-label]="c.rotulo" [title]="c.rotulo"
                (click)="escolher.emit(i)"></button>
      }
    </div>
  `,
  styles: `
    .bolinhas { display: flex; flex-wrap: wrap; gap: 8px; padding: 3px; }
    .bolinhas.em-grade { display: grid; grid-template-columns: repeat(var(--colunas), max-content); gap: 10px 14px; }
    .bolinha {
      width: 20px; height: 20px; padding: 0; border: 0; border-radius: 50%; background: var(--cor); cursor: pointer;
      transition: transform 200ms ease-out, box-shadow 200ms ease-out;
    }
    .bolinha.pequeno { width: 16px; height: 16px; }
    .bolinha.grande { width: 24px; height: 24px; }
    .bolinha:active { transform: scale(0.9); }
    .bolinha.escolhida { box-shadow: inset 0 0 0 2px var(--cor-ffffff, #fff), 0 0 0 2px var(--cor); }
    .bolinha:focus-visible { outline: 2px solid var(--botao-copiar-cor, #0a0a0a); outline-offset: 3px; }
    @media (prefers-reduced-motion: reduce) { .bolinha { transition: none; } }
  `,
})
export class SeletorCorComponent {
  readonly cores = input.required<CorSelecionavel[]>();
  /** Índice da cor escolhida. */
  readonly valor = input<number | null>(null);
  readonly tamanho = input<'pequeno' | 'padrao' | 'grande'>('padrao');
  readonly rotulo = input('Cor');
  /** Com valor maior que 0, organiza as bolinhas em grade com esse número de colunas (em vez de quebrar linha onde der). */
  readonly colunas = input(0);
  readonly escolher = output<number>();
}
