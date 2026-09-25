// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar os ícones em SVG usados na barra lateral e nos menus.

import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Nomes dos ícones disponíveis; usar um nome fora desta lista dá erro de compilação. */
export type NomeIcone =
  | 'inicio'
  | 'grade'
  | 'codigo'
  | 'arquivo'
  | 'usuarios'
  | 'usuario'
  | 'engrenagem'
  | 'alfinete'
  | 'externo'
  | 'sair'
  | 'banco-dados'
  | 'organograma'
  | 'escudo';

/** Ícones de traço (24x24) no padrão visual da barra lateral. */
@Component({
  selector: 'app-icone',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      @switch (nome()) {
        @case ('inicio') { <path d="M3 11 12 3l9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1v-9Z" /> }
        @case ('grade') {
          <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
        }
        @case ('codigo') { <path d="m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16" /> }
        @case ('arquivo') { <path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5Zm0 0v5h5M9 13h6M9 17h6" /> }
        @case ('usuarios') {
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8m13 10v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
        }
        @case ('usuario') { <path d="M20 21a8 8 0 0 0-16 0M12 13a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z" /> }
        @case ('engrenagem') {
          <circle cx="12" cy="12" r="3.5" />
          <path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1" />
        }
        @case ('alfinete') { <path d="m9 4 6 0-1 6 3 3v1H7v-1l3-3-1-6Zm3 10v6" /> }
        @case ('externo') { <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /> }
        @case ('sair') { <path d="M15 17l5-5-5-5M20 12H9M12 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h7" /> }
        @case ('banco-dados') {
          <ellipse cx="12" cy="5" rx="8" ry="3" />
          <path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" />
        }
        @case ('organograma') {
          <rect x="9" y="2" width="6" height="5" rx="1" /><rect x="2" y="17" width="6" height="5" rx="1" />
          <rect x="16" y="17" width="6" height="5" rx="1" /><path d="M12 7v5M5 17v-5h14v5" />
        }
        @case ('escudo') { <path d="M12 3 20 6v6c0 5-3.4 8.2-8 9-4.6-.8-8-4-8-9V6l8-3Z" /><path d="m9 12 2 2 4-5" /> }
      }
    </svg>
  `,
  styles: `
    :host { display: inline-flex; }
    svg { width: 100%; height: 100%; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linejoin: round; stroke-linecap: round; }
  `,
})
export class IconeComponent {
  // `input.required`: o nome do ícone é obrigatório em <app-icone nome="...">
  readonly nome = input.required<NomeIcone>();
}
