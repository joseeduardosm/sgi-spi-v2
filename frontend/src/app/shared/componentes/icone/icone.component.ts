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
  | 'escudo'
  | 'envelope'
  | 'sino'
  | 'megafone'
  | 'ajuda'
  // Lucide (https://lucide.dev, licença ISC: Copyright (c) Lucide Contributors 2022; Feather, MIT, Cole Bemis 2013-2022), sem alteração
  | 'chamado' | 'concluido' | 'relogio' | 'ampulheta' | 'recarregar' | 'grafico-colunas' | 'estrela' | 'etiqueta' | 'calendario'
  | 'predio' | 'baixar' | 'alerta';

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
        @case ('sino') { <path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15L6 16Z" /><path d="M10 20a2 2 0 0 0 4 0" /> }
        @case ('megafone') { <path d="M3 10v4a1 1 0 0 0 1 1h3l6 4V5L7 9H4a1 1 0 0 0-1 1Z" /><path d="M17 9a4 4 0 0 1 0 6M7 15l1 5h3l-1-4" /> }
        @case ('ajuda') { <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="3.5" /><path d="m5.6 5.6 3.9 3.9M14.5 14.5l3.9 3.9M18.4 5.6l-3.9 3.9M9.5 14.5l-3.9 3.9" /> }
        @case ('envelope') { <rect x="3" y="5" width="18" height="14" rx="1.5" /><path d="m3.5 6 8.5 7 8.5-7" /> }
        <!-- Lucide (ISC) -->
        @case ('chamado') { <path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z" /><path d="M13 5v2" /><path d="M13 17v2" /><path d="M13 11v2" /> }
        @case ('concluido') { <circle cx="12" cy="12" r="10" /><path d="m9 12 2 2 4-4" /> }
        @case ('relogio') { <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /> }
        @case ('ampulheta') { <path d="M5 22h14" /><path d="M5 2h14" /><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22" /><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2" /> }
        @case ('recarregar') { <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" /> }
        @case ('grafico-colunas') { <path d="M3 3v16a2 2 0 0 0 2 2h16" /><path d="M18 17V9" /><path d="M13 17V5" /><path d="M8 17v-3" /> }
        @case ('estrela') { <path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z" /> }
        @case ('etiqueta') { <path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z" /><circle cx="7.5" cy="7.5" r=".5" fill="currentColor" /> }
        @case ('calendario') { <path d="M8 2v4" /><path d="M16 2v4" /><rect width="18" height="18" x="3" y="4" rx="2" /><path d="M3 10h18" /> }
        @case ('predio') { <path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z" /><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2" /><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2" /><path d="M10 6h4" /><path d="M10 10h4" /><path d="M10 14h4" /><path d="M10 18h4" /> }
        @case ('baixar') { <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" x2="12" y1="15" y2="3" /> }
        @case ('alerta') { <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" /><path d="M12 9v4" /><path d="M12 17h.01" /> }
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
