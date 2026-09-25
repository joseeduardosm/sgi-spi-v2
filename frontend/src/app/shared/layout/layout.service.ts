// Criado por José Eduardo Santana Martins
// Este arquivo serve para guardar o estado visual do layout (barra lateral fixada, expandida e menus).

import { computed, Injectable, signal } from '@angular/core';

// Chave do localStorage onde fica a preferência "barra lateral fixada"
const CHAVE_FIXADA = 'contratos-spi.barra-lateral-fixada';

/** Lê a preferência salva; se o navegador bloquear o armazenamento, assume "não fixada". */
function lerFixada(): boolean {
  try {
    return localStorage.getItem(CHAVE_FIXADA) === 'true';
  } catch {
    return false;
  }
}

/** Estado visual do layout autenticado (barra lateral e menus). */
@Injectable({ providedIn: 'root' })
export class LayoutService {
  // Signals compartilhados entre o layout e a barra lateral
  readonly barraFixada = signal(lerFixada());
  readonly barraSobMouse = signal(false);
  readonly menuCelularAberto = signal(false);
  readonly menuUsuarioAberto = signal(false);

  /** Expandida quando fixada, sob o mouse/foco ou aberta como gaveta no celular. */
  readonly barraExpandida = computed(() => this.barraFixada() || this.barraSobMouse() || this.menuCelularAberto());

  /** Fixa ou solta a barra lateral e salva a preferência no navegador. */
  alternarFixacao(): void {
    this.barraFixada.update((v) => !v);
    try {
      localStorage.setItem(CHAVE_FIXADA, String(this.barraFixada()));
    } catch {
      // preferência vale só para esta aba
    }
  }

  /** Fecha o menu do celular e o menu do usuário (ao navegar, apertar Esc etc.). */
  fecharSobreposicoes(): void {
    this.menuCelularAberto.set(false);
    this.menuUsuarioAberto.set(false);
  }
}
