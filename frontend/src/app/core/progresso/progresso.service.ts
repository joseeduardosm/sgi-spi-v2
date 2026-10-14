// Criado por José Eduardo Santana Martins
// Este arquivo serve para saber se o sistema está trabalhando (navegação ou requisições) e mostrar a barra de progresso do topo sem piscar.

import { computed, inject, Injectable, signal } from '@angular/core';
import { NavigationCancel, NavigationEnd, NavigationError, NavigationStart, Router } from '@angular/router';

/** Só mostra a barra se o trabalho passar de 150 ms (respostas rápidas não piscam) e, uma vez mostrada, a mantém por pelo menos 300 ms. */
export const ATRASO_MS = 150;
export const MINIMO_VISIVEL_MS = 300;

@Injectable({ providedIn: 'root' })
export class ProgressoService {
  private readonly requisicoes = signal(0);
  private readonly navegando = signal(false);
  private readonly _envio = signal<number | null>(null);
  private readonly _visivel = signal(false);
  private mostradaEm = 0;
  private temporizador: ReturnType<typeof setTimeout> | null = null;

  /** Há algo em andamento (antes do atraso e do tempo mínimo). */
  readonly ocupado = computed(() => this.requisicoes() > 0 || this.navegando());
  /** Percentual (0 a 100) do envio de arquivo em andamento, ou nulo quando o progresso é indeterminado. */
  readonly envio = this._envio.asReadonly();
  /** A barra deve aparecer agora. */
  readonly visivel = this._visivel.asReadonly();

  constructor() {
    // O roteador pode não existir em testes isolados: nesse caso só as requisições contam
    const roteador = inject(Router, { optional: true });
    roteador?.events.subscribe((evento) => {
      if (evento instanceof NavigationStart) this.navegando.set(true);
      else if (evento instanceof NavigationEnd || evento instanceof NavigationCancel || evento instanceof NavigationError) this.navegando.set(false);
      this.avaliar();
    });
  }

  iniciarRequisicao(): void {
    this.requisicoes.update((n) => n + 1);
    this.avaliar();
  }

  terminarRequisicao(): void {
    this.requisicoes.update((n) => Math.max(0, n - 1));
    this.avaliar();
  }

  /** Informa o andamento de um envio de arquivo (`carregado` de `total` bytes); `null` ao terminar. */
  informarEnvio(carregado: number | null, total?: number): void {
    this._envio.set(carregado === null || !total ? null : Math.min(100, Math.round((carregado / total) * 100)));
  }

  private limpar(): void {
    if (this.temporizador) { clearTimeout(this.temporizador); this.temporizador = null; }
  }

  private avaliar(): void {
    if (this.ocupado()) {
      if (this._visivel() || this.temporizador) return;
      this.temporizador = setTimeout(() => {
        this.temporizador = null;
        if (this.ocupado()) { this.mostradaEm = Date.now(); this._visivel.set(true); }
      }, ATRASO_MS);
      return;
    }
    this.limpar();
    if (!this._visivel()) return;
    const restante = Math.max(0, MINIMO_VISIVEL_MS - (Date.now() - this.mostradaEm));
    this.temporizador = setTimeout(() => {
      this.temporizador = null;
      if (!this.ocupado()) this._visivel.set(false);
    }, restante);
  }
}
