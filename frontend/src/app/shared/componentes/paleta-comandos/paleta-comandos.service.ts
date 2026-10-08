// Criado por José Eduardo Santana Martins
// Este arquivo serve para abrir e fechar a paleta de comandos (Ctrl+K) de qualquer ponto do portal.

import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class PaletaComandosService {
  /** A paleta está aberta? */
  readonly aberta = signal(false);

  abrir(): void {
    this.aberta.set(true);
  }

  fechar(): void {
    this.aberta.set(false);
  }

  alternar(): void {
    this.aberta.update((v) => !v);
  }
}
