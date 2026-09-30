// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o slider de notícias da página inicial (passagem automática, setas, pontos, toque e teclado).

import { Component, computed, DestroyRef, effect, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { dataCurta, NoticiaCartao, srcsetCapa } from '../noticias.models';

/** Slider 2:1. Pausa com o mouse ou o foco em cima, respeita "reduzir movimento" e aceita setas do teclado e deslizar no celular. */
@Component({
  selector: 'app-slider-noticias',
  imports: [RouterLink],
  host: { '(keydown.arrowleft)': 'anterior()', '(keydown.arrowright)': 'proximo()' },
  template: `
    @if (slides().length) {
      <section class="slider-noticias" aria-roledescription="carrossel" aria-label="Destaques"
               (mouseenter)="pausado.set(true)" (mouseleave)="pausado.set(false)" (focusin)="pausado.set(true)" (focusout)="pausado.set(false)"
               (touchstart)="inicioToque = $any($event).touches[0].clientX" (touchend)="fimToque($any($event).changedTouches[0].clientX)">
        <div class="trilho-slider" [style.transform]="'translateX(-' + atual() * 100 + '%)'">
          @for (n of slides(); track n.id; let i = $index) {
            <a class="slide" [routerLink]="['/noticias', n.slug]" [attr.aria-hidden]="i !== atual()" [attr.tabindex]="i === atual() ? 0 : -1"
               role="group" aria-roledescription="slide" [attr.aria-label]="(i + 1) + ' de ' + slides().length + ': ' + n.titulo">
              @if (n.capa['1600']) {
                <img [src]="n.capa['1600']" [srcset]="srcset(n)" sizes="(max-width: 900px) 100vw, 900px" [alt]="n.capa_alt"
                     [attr.loading]="i === 0 ? 'eager' : 'lazy'" />
              } @else { <div class="slide-sem-capa"></div> }
              @if (tituloSobreposto()) {
                <div class="legenda-slide">
                  @if (n.categoria) { <span class="chip-categoria" [style.--cor]="n.categoria.cor">{{ n.categoria.nome }}</span> }
                  <strong>{{ n.titulo }}</strong>
                  <small>{{ data(n.publicada_em) }}</small>
                </div>
              }
            </a>
          }
        </div>
        @if (slides().length > 1) {
          <button type="button" class="seta-slider anterior" aria-label="Notícia anterior" (click)="anterior()">‹</button>
          <button type="button" class="seta-slider proxima" aria-label="Próxima notícia" (click)="proximo()">›</button>
          <div class="pontos-slider" role="tablist" aria-label="Escolher destaque">
            @for (n of slides(); track n.id; let i = $index) {
              <button type="button" role="tab" [class.ativo]="i === atual()" [attr.aria-selected]="i === atual()"
                      [attr.aria-label]="'Destaque ' + (i + 1)" (click)="irPara(i)"></button>
            }
          </div>
        }
      </section>
    }
  `,
})
export class SliderNoticiasComponent {
  readonly slides = input<NoticiaCartao[]>([]);
  readonly segundos = input(7);
  readonly automatico = input(true);
  readonly tituloSobreposto = input(true);
  protected readonly atual = signal(0);
  protected readonly pausado = signal(false);
  protected inicioToque = 0;
  protected readonly data = dataCurta;
  protected readonly srcset = (n: NoticiaCartao) => srcsetCapa(n.capa);
  private readonly reduzido = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  private readonly total = computed(() => this.slides().length);

  constructor() {
    let relogio: ReturnType<typeof setInterval> | null = null;
    // Recria o temporizador quando mudam os slides, o tempo ou a pausa
    effect(() => {
      if (relogio) clearInterval(relogio);
      relogio = null;
      if (!this.automatico() || this.reduzido || this.pausado() || this.total() < 2) return;
      relogio = setInterval(() => this.proximo(), Math.max(3, this.segundos()) * 1000);
    });
    inject(DestroyRef).onDestroy(() => relogio && clearInterval(relogio));
  }

  protected proximo(): void {
    this.atual.update((i) => (i + 1) % Math.max(1, this.total()));
  }

  protected anterior(): void {
    this.atual.update((i) => (i - 1 + this.total()) % Math.max(1, this.total()));
  }

  protected irPara(i: number): void {
    this.atual.set(i);
  }

  protected fimToque(x: number): void {
    const delta = x - this.inicioToque;
    if (Math.abs(delta) > 40) (delta < 0 ? this.proximo() : this.anterior());
  }
}
