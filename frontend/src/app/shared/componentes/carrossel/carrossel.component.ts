// Criado por José Eduardo Santana Martins
// Este arquivo serve para girar painéis em carrossel (passagem automática, pausa, setas, pontos, toque e teclado) com o conteúdo projetado.

import { ChangeDetectionStrategy, Component, DestroyRef, effect, inject, input, model, signal } from '@angular/core';

/**
 * Carrossel genérico: cada filho direto do conteúdo vira um slide de 100% da largura.
 * Informe `total` (quantos slides há) e, opcionalmente, `rotulos` para os pontos de navegação.
 * Pausa com o mouse/foco em cima, respeita "reduzir movimento" e aceita setas do teclado e deslizar no celular.
 */
@Component({
  selector: 'app-carrossel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(keydown.arrowleft)': 'anterior()', '(keydown.arrowright)': 'proximo()' },
  template: `
    <section class="carrossel" aria-roledescription="carrossel" [attr.aria-label]="descricao()" tabindex="0"
             (mouseenter)="sobre.set(true)" (mouseleave)="sobre.set(false)" (focusin)="sobre.set(true)" (focusout)="sobre.set(false)"
             (touchstart)="inicioToque = $any($event).touches[0].clientX" (touchend)="fimToque($any($event).changedTouches[0].clientX)">
      <div class="trilho-carrossel" [style.transform]="'translateX(-' + atual() * 100 + '%)'" aria-live="off">
        <ng-content />
      </div>
      @if (total() > 1) {
        <button type="button" class="seta-carrossel anterior" aria-label="Painel anterior" (click)="anterior()">‹</button>
        <button type="button" class="seta-carrossel proxima" aria-label="Próximo painel" (click)="proximo()">›</button>
        <div class="pontos-carrossel" role="tablist" aria-label="Escolher painel">
          @for (i of indices(); track i) {
            <button type="button" role="tab" [class.ativo]="i === atual()" [attr.aria-selected]="i === atual()"
                    [attr.aria-label]="rotulos()[i] ?? 'Painel ' + (i + 1)" [title]="rotulos()[i] ?? ''" (click)="irPara(i)"></button>
          }
        </div>
      }
    </section>
  `,
})
export class CarrosselComponent {
  readonly total = input.required<number>();
  readonly rotulos = input<string[]>([]);
  readonly descricao = input('Painéis');
  readonly segundos = input(12);
  readonly automatico = input(true);
  /** Índice do slide em exibição (permite ao pai saber qual painel está na tela). */
  readonly atual = model(0);
  /** Pausa pedida pelo usuário (botão do pai). */
  readonly pausado = input(false);
  protected readonly sobre = signal(false);
  protected inicioToque = 0;
  private readonly reduzido = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  protected indices(): number[] {
    return Array.from({ length: this.total() }, (_, i) => i);
  }

  constructor() {
    let relogio: ReturnType<typeof setInterval> | null = null;
    // Recria o temporizador quando mudam o tempo, a pausa ou a quantidade de slides
    effect(() => {
      if (relogio) clearInterval(relogio);
      relogio = null;
      if (!this.automatico() || this.reduzido || this.pausado() || this.sobre() || this.total() < 2) return;
      relogio = setInterval(() => this.proximo(), Math.max(4, this.segundos()) * 1000);
    });
    inject(DestroyRef).onDestroy(() => relogio && clearInterval(relogio));
  }

  proximo(): void {
    this.atual.update((i) => (i + 1) % Math.max(1, this.total()));
  }

  anterior(): void {
    this.atual.update((i) => (i - 1 + this.total()) % Math.max(1, this.total()));
  }

  irPara(i: number): void {
    this.atual.set(i);
  }

  protected fimToque(x: number): void {
    const delta = x - this.inicioToque;
    if (Math.abs(delta) > 40) (delta < 0 ? this.proximo() : this.anterior());
  }
}
