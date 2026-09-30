// Criado por José Eduardo Santana Martins
// Este arquivo serve para enquadrar a capa em 2:1 no próprio editor (arrastar e zoom) ou mostrá-la inteira, sem cortes.

import { Component, computed, ElementRef, input, model, output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ModoCapa } from '../noticias.models';

export interface Recorte { x: number; y: number; largura: number; altura: number }

/**
 * A moldura tem sempre a proporção 2:1. A imagem cobre a moldura; arrastar move o enquadramento e o controle deslizante
 * (ou a roda do mouse) aproxima. O recorte sai em pixels da imagem original, que é o que o servidor aplica.
 */
@Component({
  selector: 'app-recorte-capa',
  imports: [FormsModule],
  template: `
    <div class="recorte-capa">
      <div class="modos-capa" role="radiogroup" aria-label="Como usar a imagem">
        <label [class.ativo]="modo() === 'recortar'"><input type="radio" name="modo-capa" [checked]="modo() === 'recortar'" (change)="trocarModo('recortar')" />
          Enquadrar em 2:1 <small>arraste e aproxime para escolher o trecho</small></label>
        <label [class.ativo]="modo() === 'inteira'"><input type="radio" name="modo-capa" [checked]="modo() === 'inteira'" (change)="trocarModo('inteira')" />
          Imagem inteira <small>sem cortes, sobre fundo desfocado (bom para cartazes com texto)</small></label>
      </div>
      <div #moldura class="moldura-capa" [class.inteira]="modo() === 'inteira'" (pointerdown)="iniciar($event)" (pointermove)="mover($event)"
           (pointerup)="soltar()" (pointercancel)="soltar()" (wheel)="roda($event)">
        @if (url(); as u) {
          @if (modo() === 'inteira') {
            <img class="fundo-inteira" [src]="u" alt="" />
            <img class="frente-inteira" [src]="u" alt="Prévia da capa" />
          } @else {
            <img class="imagem-recorte" [src]="u" alt="Prévia da capa" draggable="false" (load)="aoCarregar($event)"
                 [style.width.px]="larguraExibida()" [style.transform]="'translate(' + ox() + 'px,' + oy() + 'px)'" />
          }
        }
        @if (modo() === 'recortar') { <span class="guia-capa" aria-hidden="true">Arraste para enquadrar</span> }
      </div>
      @if (modo() === 'recortar') {
        <div class="zoom-capa">
          <label for="zoom-capa">Aproximar</label>
          <input id="zoom-capa" type="range" min="1" max="4" step="0.01" [ngModel]="zoom()" (ngModelChange)="aplicarZoom($event)" />
        </div>
      }
      @if (baixaResolucao()) { <p class="aviso-formulario">O trecho escolhido tem menos de 800 px de largura: a capa pode ficar borrada no slider.</p> }
    </div>
  `,
})
export class RecorteCapaComponent {
  readonly url = input<string | null>(null);
  readonly modo = model<ModoCapa>('recortar');
  readonly inicial = input<Recorte | null>(null);
  readonly alterado = output<Recorte | null>();
  private readonly moldura = viewChild<ElementRef<HTMLDivElement>>('moldura');

  private natural = { w: 0, h: 0 };
  private readonly largura = signal(0);
  protected readonly escala = signal(1);
  protected readonly zoom = signal(1);
  protected readonly ox = signal(0);
  protected readonly oy = signal(0);
  private arrasto: { x: number; y: number; ox: number; oy: number } | null = null;
  protected readonly larguraExibida = computed(() => this.natural.w * this.escala());
  protected readonly baixaResolucao = computed(() => this.modo() === 'recortar' && this.natural.w > 0 && this.largura() / this.escala() < 800);

  private escalaMinima(): number {
    const W = this.largura();
    return Math.max(W / this.natural.w, W / 2 / this.natural.h);
  }

  protected aoCarregar(evento: Event): void {
    const img = evento.target as HTMLImageElement;
    this.natural = { w: img.naturalWidth, h: img.naturalHeight };
    this.largura.set(this.moldura()!.nativeElement.clientWidth);
    const r = this.inicial();
    const minima = this.escalaMinima();
    if (r && r.largura > 0) {
      const s = Math.max(minima, this.largura() / r.largura);
      this.escala.set(s); this.zoom.set(s / minima);
      this.ox.set(-r.x * s); this.oy.set(-r.y * s);
      this.limitar();
    } else {
      this.escala.set(minima); this.zoom.set(1);
      this.ox.set((this.largura() - this.natural.w * minima) / 2); this.oy.set((this.largura() / 2 - this.natural.h * minima) / 2);
      this.emitir();
    }
  }

  protected trocarModo(m: ModoCapa): void {
    this.modo.set(m);
    this.emitir();
  }

  protected iniciar(e: PointerEvent): void {
    if (this.modo() !== 'recortar') return;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    this.arrasto = { x: e.clientX, y: e.clientY, ox: this.ox(), oy: this.oy() };
  }

  protected mover(e: PointerEvent): void {
    if (!this.arrasto) return;
    this.ox.set(this.arrasto.ox + e.clientX - this.arrasto.x);
    this.oy.set(this.arrasto.oy + e.clientY - this.arrasto.y);
    this.limitar();
  }

  protected soltar(): void {
    if (this.arrasto) { this.arrasto = null; this.emitir(); }
  }

  protected roda(e: WheelEvent): void {
    if (this.modo() !== 'recortar') return;
    e.preventDefault();
    this.aplicarZoom(Math.min(4, Math.max(1, this.zoom() * (e.deltaY < 0 ? 1.08 : 0.92))));
  }

  /** Aproxima mantendo o centro da moldura no mesmo ponto da imagem. */
  protected aplicarZoom(z: number): void {
    const W = this.largura(), H = W / 2, antiga = this.escala(), nova = this.escalaMinima() * z;
    const cx = (W / 2 - this.ox()) / antiga, cy = (H / 2 - this.oy()) / antiga;
    this.zoom.set(z); this.escala.set(nova);
    this.ox.set(W / 2 - cx * nova); this.oy.set(H / 2 - cy * nova);
    this.limitar();
    this.emitir();
  }

  private limitar(): void {
    const W = this.largura(), H = W / 2, s = this.escala();
    this.ox.set(Math.min(0, Math.max(W - this.natural.w * s, this.ox())));
    this.oy.set(Math.min(0, Math.max(H - this.natural.h * s, this.oy())));
  }

  private emitir(): void {
    if (this.modo() === 'inteira' || !this.natural.w) { this.alterado.emit(null); return; }
    const s = this.escala(), W = this.largura();
    this.alterado.emit({ x: Math.round(-this.ox() / s), y: Math.round(-this.oy() / s), largura: Math.round(W / s), altura: Math.round(W / 2 / s) });
  }
}
