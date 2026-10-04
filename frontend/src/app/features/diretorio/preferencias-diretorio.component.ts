// Criado por José Eduardo Santana Martins
// Este arquivo serve para abrir, na tela de Ramais, a janela de foto e privacidade do usuário.

import { Component, output } from '@angular/core';

import { FotoPerfilComponent } from './foto-perfil.component';

@Component({
  selector: 'app-preferencias-diretorio',
  imports: [FotoPerfilComponent],
  template: `
    <div class="fundo-modal" (click)="fechar.emit()"></div>
    <section class="modal-portal" role="dialog" aria-modal="true" aria-label="Minha foto e privacidade">
      <header><h2>Minha foto e privacidade</h2><button type="button" class="fechar" aria-label="Fechar" (click)="fechar.emit()">×</button></header>
      <app-foto-perfil (alterou)="alterou.emit()" />
      <footer><button type="button" class="acao-primaria" (click)="fechar.emit()">Fechar</button></footer>
    </section>
  `,
})
export class PreferenciasDiretorioComponent {
  readonly fechar = output<void>();
  /** Avisa a tela que a foto mudou, para recarregar os cartões. */
  readonly alterou = output<void>();
}
