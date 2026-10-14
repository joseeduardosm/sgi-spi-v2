// Criado por José Eduardo Santana Martins
// Este arquivo serve para a barra fina de progresso no topo da tela (aparece quando o sistema está carregando algo).

import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { ProgressoService } from '../../../core/progresso/progresso.service';

/** Barra indeterminada de 3 px no topo. Entra e sai só com opacidade; o deslize usa `transform` com easing linear. Com "reduzir movimento" fica uma faixa fixa. */
@Component({
  selector: 'app-barra-progresso',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (progresso.visivel()) {
      <div class="barra-topo" role="progressbar" aria-label="Carregando" aria-busy="true" [attr.aria-valuenow]="progresso.envio()" aria-valuemin="0" aria-valuemax="100"
           [class.determinada]="progresso.envio() !== null" [style.--envio]="(progresso.envio() ?? 0) / 100" animate.enter="mov-fundo-entra" animate.leave="mov-fundo-sai"><span></span></div>
    }
  `,
  styles: `
    .barra-topo { position: fixed; inset: 0 0 auto 0; z-index: 1000; height: 3px; overflow: hidden; pointer-events: none; background: rgba(200, 35, 49, 0.15); }
    .barra-topo span { display: block; width: 33%; height: 100%; background: var(--spi-vermelho, #c82331); animation: prog-indeterminado 1.1s linear infinite; }
    /* Envio de arquivo: a barra cresce com o percentual (scaleX, linear) em vez de deslizar */
    .barra-topo.determinada span { width: 100%; animation: none; transform-origin: left; transform: scaleX(var(--envio, 0)); transition: transform var(--mov-padrao) linear; }
    @media (prefers-reduced-motion: reduce) { .barra-topo span { width: 100%; animation: none; } }
  `,
})
export class BarraProgressoComponent {
  protected readonly progresso = inject(ProgressoService);
}
