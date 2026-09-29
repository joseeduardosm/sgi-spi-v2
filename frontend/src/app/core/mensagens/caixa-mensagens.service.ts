// Criado por José Eduardo Santana Martins
// Este arquivo serve para manter o estado do sino (pendentes) e a janela de aviso aberta pela mensageria.

import { DestroyRef, inject, Injectable, signal } from '@angular/core';

import { AutenticacaoService } from '../autenticacao/autenticacao.service';
import { MensagensApiService } from './mensagens-api.service';
import { EntregaDetalhe } from './mensagens.models';

/** Intervalo da consulta do sino. */
const INTERVALO_MS = 60_000;

/**
 * Contador do sino e janela de aviso (ex.: "Você foi cadastrado como Gestor…"). Consulta `/resumo` ao
 * iniciar, a cada minuto e sempre que uma tela pede `atualizar()`. Nada aqui bloqueia a navegação.
 */
@Injectable({ providedIn: 'root' })
export class CaixaMensagensService {
  private readonly api = inject(MensagensApiService);
  private readonly autenticacao = inject(AutenticacaoService);

  readonly pendentes = signal(0);
  readonly janela = signal<EntregaDetalhe | null>(null);
  private relogio: ReturnType<typeof setInterval> | null = null;

  /** Começa a acompanhar a caixa (chamado pelo layout autenticado). */
  iniciar(destruir: DestroyRef): void {
    this.atualizar();
    this.relogio ??= setInterval(() => this.atualizar(), INTERVALO_MS);
    destruir.onDestroy(() => {
      if (this.relogio) clearInterval(this.relogio);
      this.relogio = null;
    });
  }

  /** Busca o resumo; com o perfil pendente (acesso restrito) não consulta. */
  atualizar(): void {
    const usuario = this.autenticacao.usuario();
    if (!usuario || usuario.perfil_restrito) return;
    this.api.resumo().subscribe({
      next: (r) => {
        this.pendentes.set(r.pendentes);
        // Não troca a janela que já está aberta
        if (!this.janela() && r.janela) this.janela.set(r.janela);
      },
      error: () => undefined,
    });
  }
}
