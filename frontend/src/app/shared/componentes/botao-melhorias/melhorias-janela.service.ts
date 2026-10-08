// Criado por José Eduardo Santana Martins
// Este arquivo serve para pedir a abertura da janela "Sugerir melhoria" de fora do botão flutuante (ex.: paleta de comandos).

import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class MelhoriasJanelaService {
  /** Contador de pedidos de abertura: o botão flutuante abre a janela sempre que ele muda. */
  readonly pedidos = signal(0);

  pedirAbertura(): void {
    this.pedidos.update((n) => n + 1);
  }
}
