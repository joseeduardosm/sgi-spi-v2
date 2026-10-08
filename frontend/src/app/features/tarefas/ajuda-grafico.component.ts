// Criado por José Eduardo Santana Martins
// Este arquivo serve para o botão discreto "?" dos gráficos do Desempenho: ao clicar, abre uma explicação em linguagem simples.

import { Component, ElementRef, HostListener, inject, input, signal } from '@angular/core';

/** Texto de ajuda de um gráfico: o que mostra, como ler e o que observar. */
export interface AjudaGrafico { titulo: string; oQueE: string; comoLer: string; atencao: string }

@Component({
  selector: 'app-ajuda-grafico',
  template: `
    <button type="button" class="botao-ajuda-grafico" [attr.aria-expanded]="aberta()" [attr.aria-label]="'Como ler: ' + ajuda().titulo"
            title="Como ler este gráfico" (click)="alternar($event)">?</button>
    @if (aberta()) {
      <div class="balao-ajuda-grafico" role="dialog" [attr.aria-label]="'Como ler: ' + ajuda().titulo">
        <strong>{{ ajuda().titulo }}</strong>
        <p><b>O que é.</b> {{ ajuda().oQueE }}</p>
        <p><b>Como ler.</b> {{ ajuda().comoLer }}</p>
        <p><b>Fique de olho.</b> {{ ajuda().atencao }}</p>
      </div>
    }
  `,
})
export class AjudaGraficoComponent {
  readonly ajuda = input.required<AjudaGrafico>();
  protected readonly aberta = signal(false);
  private readonly eu = inject<ElementRef<HTMLElement>>(ElementRef);

  protected alternar(evento: Event): void {
    evento.stopPropagation();
    this.aberta.update((v) => !v);
  }

  /** Clicar fora ou apertar Esc fecha o balão. */
  @HostListener('document:click', ['$event'])
  protected fora(evento: Event): void {
    if (!this.eu.nativeElement.contains(evento.target as Node)) this.aberta.set(false);
  }

  @HostListener('document:keydown.escape')
  protected esc(): void {
    this.aberta.set(false);
  }
}
