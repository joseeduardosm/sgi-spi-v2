// Criado por José Eduardo Santana Martins
// Este arquivo serve para avisar que um rascunho guardado no navegador foi restaurado no formulário, com a opção de descartá-lo.

import { DatePipe } from '@angular/common';
import { Component, input, output } from '@angular/core';

/** Aviso "Rascunho restaurado" dos formulários que guardam rascunho (ver `RascunhoService`). */
@Component({
  selector: 'app-aviso-rascunho',
  imports: [DatePipe],
  template: `
    <p class="aviso-formulario aviso-rascunho" role="status">
      <span>Rascunho restaurado (salvo em {{ salvoEm() | date: 'dd/MM/yyyy HH:mm' }}). {{ observacao() }}</span>
      <button type="button" class="acao-secundaria acao-pequena" (click)="descartar.emit()">Descartar rascunho</button>
    </p>
  `,
})
export class AvisoRascunhoComponent {
  readonly salvoEm = input.required<string>();
  /** Complemento do aviso (ex.: que os anexos não são guardados). */
  readonly observacao = input('');
  readonly descartar = output<void>();
}
