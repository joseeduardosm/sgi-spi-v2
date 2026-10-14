// Criado por José Eduardo Santana Martins
// Este arquivo serve para oferecer o botão "copiar" padrão do sistema (ícone que troca por um visto com efeito de desfoque, inspirado no Copy Button do Spell).

import { ChangeDetectionStrategy, Component, DestroyRef, inject, input, output, signal } from '@angular/core';

/**
 * Botão de copiar: o ícone de cópia dá lugar a um visto por 1,5 s, com escala, opacidade e desfoque (200 ms).
 * Traços pretos no tema claro e brancos no escuro (`currentColor` + `--botao-copiar-cor`).
 * Sem `valor`, só avisa por `acionar` (para cópias especiais, como HTML formatado).
 */
@Component({
  selector: 'app-botao-copiar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" class="botao-copiar" [class.com-rotulo]="!!rotulo()" [class.pequeno]="tamanho() === 'pequeno'" [class.grande]="tamanho() === 'grande'"
            [disabled]="copiado() || desabilitado()" [attr.aria-label]="copiado() ? 'Copiado' : (titulo() || rotulo() || 'Copiar')"
            [title]="copiado() ? 'Copiado!' : (titulo() || rotulo() || 'Copiar')" (click)="copiar($event)">
      <span class="icones" aria-hidden="true">
        <svg class="icone-visto" [class.visivel]="copiado()" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
        <svg class="icone-copia" [class.visivel]="!copiado()" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
      </span>
      @if (rotulo()) { <span class="texto">{{ copiado() ? 'Copiado' : rotulo() }}</span> }
    </button>
  `,
  styles: `
    :host { display: inline-flex; }
    .botao-copiar {
      --lado: 36px; --icone: 16px;
      position: relative; display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-width: var(--lado); height: var(--lado); padding: 0;
      border: 0; border-radius: var(--spi-raio-p); background: none; color: var(--botao-copiar-cor, #0a0a0a); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer;
      transition: transform 200ms ease-out, background-color 200ms ease-out;
    }
    .botao-copiar.pequeno { --lado: 28px; --icone: 14px; }
    .botao-copiar.grande { --lado: 44px; --icone: 20px; }
    .botao-copiar.com-rotulo { padding: 0 10px; }
    .botao-copiar:hover:not(:disabled) { background: color-mix(in srgb, currentColor 8%, transparent); }
    .botao-copiar:active:not(:disabled) { transform: scale(0.97); }
    .botao-copiar:disabled { cursor: default; opacity: 1; pointer-events: none; }
    .botao-copiar:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
    .icones { position: relative; display: inline-grid; place-items: center; width: var(--icone); height: var(--icone); flex: none; }
    svg { grid-area: 1 / 1; width: var(--icone); height: var(--icone); opacity: 0; transform: scale(0.7); filter: blur(2px); transition: opacity 200ms ease-out, transform 200ms ease-out, filter 200ms ease-out; }
    svg.visivel { opacity: 1; transform: scale(1); filter: none; }
    .icone-copia:not(.visivel) { transform: scale(0); }
    @media (prefers-reduced-motion: reduce) { .botao-copiar, svg { transition: none; } }
  `,
})
export class BotaoCopiarComponent {
  /** Texto a copiar; sem ele, o botão só emite `acionar`. */
  readonly valor = input<string | null | undefined>(null);
  /** Texto ao lado do ícone (ex.: "Copiar link"); sem ele, o botão é só o ícone. */
  readonly rotulo = input('');
  readonly titulo = input('');
  readonly tamanho = input<'pequeno' | 'padrao' | 'grande'>('padrao');
  readonly desabilitado = input(false);
  /** Emitido a cada clique, depois de copiar o `valor` (se houver). */
  readonly acionar = output<void>();

  protected readonly copiado = signal(false);
  private temporizador: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.temporizador));
  }

  protected copiar(evento: Event): void {
    evento.stopPropagation();
    const valor = this.valor();
    if (valor) void navigator.clipboard?.writeText(valor).catch(() => undefined);
    this.copiado.set(true);
    clearTimeout(this.temporizador);
    this.temporizador = setTimeout(() => this.copiado.set(false), 1500);
    this.acionar.emit();
  }
}
