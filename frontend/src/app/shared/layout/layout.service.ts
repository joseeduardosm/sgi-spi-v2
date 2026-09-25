import { computed, Injectable, signal } from '@angular/core';

const CHAVE_FIXADA = 'contratos-spi.barra-lateral-fixada';

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
  readonly barraFixada = signal(lerFixada());
  readonly barraSobMouse = signal(false);
  readonly menuCelularAberto = signal(false);
  readonly menuUsuarioAberto = signal(false);

  /** Expandida quando fixada, sob o mouse/foco ou aberta como gaveta no celular. */
  readonly barraExpandida = computed(() => this.barraFixada() || this.barraSobMouse() || this.menuCelularAberto());

  alternarFixacao(): void {
    this.barraFixada.update((v) => !v);
    try {
      localStorage.setItem(CHAVE_FIXADA, String(this.barraFixada()));
    } catch {
      // preferência vale só para esta aba
    }
  }

  fecharSobreposicoes(): void {
    this.menuCelularAberto.set(false);
    this.menuUsuarioAberto.set(false);
  }
}
