// Criado por José Eduardo Santana Martins
// Este arquivo serve para inclinar um cartão em 3D seguindo o ponteiro, com um foco de luz (releitura do Tilt Card do Spell).

import { DestroyRef, Directive, ElementRef, inject, input, OnInit, Renderer2 } from '@angular/core';

/**
 * Inclinação 3D do cartão ao passar o ponteiro, com foco de luz que o acompanha.
 * Não age em toque nem com movimento reduzido. O elemento precisa de `position: relative` e `overflow: hidden`.
 */
@Directive({ selector: '[appInclinar]' })
export class InclinarDirective implements OnInit {
  /** Inclinação máxima, em graus. */
  readonly limite = input(8, { alias: 'inclinarLimite' });
  readonly escala = input(1.03, { alias: 'inclinarEscala' });
  readonly perspectiva = input(1200, { alias: 'inclinarPerspectiva' });
  /** `foge` inclina para longe do ponteiro; `atrai` inclina em direção a ele. */
  readonly efeito = input<'foge' | 'atrai'>('foge', { alias: 'inclinarEfeito' });
  readonly foco = input(true, { alias: 'inclinarFoco' });

  private readonly elemento = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly renderizador = inject(Renderer2);
  private luz: HTMLElement | null = null;
  private halo: HTMLElement | null = null;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.luz?.remove());
  }

  ngOnInit(): void {
    const el = this.elemento;
    el.style.transition = 'transform 200ms ease-out, box-shadow 200ms ease-out';
    el.style.willChange = 'transform';
    el.style.transformStyle = 'preserve-3d';
    this.renderizador.listen(el, 'pointerenter', (e: PointerEvent) => this.entrar(e));
    this.renderizador.listen(el, 'pointermove', (e: PointerEvent) => this.mover(e));
    this.renderizador.listen(el, 'pointerleave', () => this.sair());
  }

  private ativo(e: PointerEvent): boolean {
    return e.pointerType === 'mouse' && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  private entrar(e: PointerEvent): void {
    if (!this.ativo(e) || !this.foco()) return;
    if (!this.luz) {
      this.luz = this.renderizador.createElement('div');
      this.halo = this.renderizador.createElement('div');
      Object.assign(this.luz!.style, { position: 'absolute', inset: '0', zIndex: '5', pointerEvents: 'none', overflow: 'hidden', opacity: '0', transition: 'opacity 300ms ease-out' });
      Object.assign(this.halo!.style, {
        position: 'absolute', width: '200%', height: '200%', borderRadius: '50%', transform: 'translate(-50%, -50%)',
        background: 'radial-gradient(circle, rgba(255,255,255,0.28) 0%, transparent 40%)',
      });
      this.luz!.setAttribute('aria-hidden', 'true');
      this.luz!.appendChild(this.halo!);
      this.elemento.appendChild(this.luz!);
    }
    if (this.luz) this.luz.style.opacity = '1';
  }

  private mover(e: PointerEvent): void {
    if (!this.ativo(e)) return;
    const r = this.elemento.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    const sentido = this.efeito() === 'foge' ? -1 : 1;
    const x = (py - 0.5) * this.limite() * 2 * sentido;
    const y = (px - 0.5) * -this.limite() * 2 * sentido;
    const esc = this.escala();
    this.elemento.style.transform = `perspective(${this.perspectiva()}px) rotateX(${x}deg) rotateY(${y}deg) scale3d(${esc}, ${esc}, ${esc})`;
    if (this.halo) { this.halo.style.left = `${px * 100}%`; this.halo.style.top = `${py * 100}%`; }
  }

  private sair(): void {
    this.elemento.style.transform = '';
    if (this.luz) this.luz.style.opacity = '0';
  }
}
