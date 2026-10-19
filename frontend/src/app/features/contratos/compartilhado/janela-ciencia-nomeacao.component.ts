// Criado por José Eduardo Santana Martins
// Este arquivo serve para pedir a ciência de quem foi nomeado em uma portaria de designação (modal ao entrar no sistema).

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { CienciaPendente } from './contratos.models';
import { PortariasApiService } from './portarias-api.service';

/**
 * Modal "Você está sendo nomeado por X como Y do contrato Z. Você está ciente?".
 * Aparece para quem tem nomeação aguardando ciência (qualquer usuário, mesmo sem acesso ao módulo). "Sim, estou ciente" registra a ciência;
 * "Ainda não" só fecha até a próxima vez que o sistema for aberto (a nomeação segue pendente e o aviso continua no sino; abri-lo reabre este pedido).
 */
@Component({
  selector: 'app-janela-ciencia-nomeacao',
  template: `
    @if (atual(); as c) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal janela-mensagem" role="alertdialog" aria-modal="true" aria-labelledby="titulo-ciencia-nomeacao">
        <header>
          <div><span class="modal-sobretitulo">Portaria de designação</span>
            <h2 id="titulo-ciencia-nomeacao">Você foi nomeado</h2></div>
        </header>
        <div class="corpo-janela-mensagem">
          Você está sendo nomeado por <strong>{{ c.nomeado_por }}</strong> como <strong>{{ c.papel_rotulo }}</strong> do contrato <strong>{{ c.contrato }}</strong>.
          Você está ciente?
        </div>
        <footer>
          <button type="button" class="acao-recusar" [disabled]="ocupado()" (click)="adiar(c)">Ainda não</button>
          <button type="button" class="acao-positiva" [class.carregando]="ocupado()" [disabled]="ocupado()" (click)="ciente(c)">Sim, estou ciente</button>
        </footer>
      </section>
    }
  `,
})
export class JanelaCienciaNomeacaoComponent implements OnInit {
  private readonly api = inject(PortariasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

  private readonly pendentes = signal<CienciaPendente[]>([]);
  /** Portarias adiadas nesta sessão (não reabrem a cada navegação). */
  private readonly adiadas = signal<Set<string>>(new Set());
  protected readonly ocupado = signal(false);
  protected readonly atual = computed(() => this.pendentes().find((c) => !this.adiadas().has(c.portaria_id)) ?? null);

  constructor() {
    // Confere de novo a cada navegação, para a janela aparecer logo depois de o pedido de ciência ser gerado
    this.roteador.events.pipe(filter((e) => e instanceof NavigationEnd), takeUntilDestroyed()).subscribe(() => {
      // Abrir o aviso do sino (link com ?ciencia=<portaria>) reabre o pedido de ciência que tinha sido adiado
      const pedida = this.roteador.parseUrl(this.roteador.url).queryParams['ciencia'];
      if (pedida) this.adiadas.update((s) => { const novo = new Set(s); novo.delete(pedida); return novo; });
      this.carregar();
    });
  }

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.api.ciencias().subscribe({ next: (lista) => this.pendentes.set(lista), error: () => undefined });
  }

  protected adiar(c: CienciaPendente): void {
    this.adiadas.update((s) => new Set(s).add(c.portaria_id));
  }

  protected ciente(c: CienciaPendente): void {
    this.ocupado.set(true);
    this.api.darCiencia(c.portaria_id).subscribe({
      next: (lista) => { this.ocupado.set(false); this.pendentes.set(lista); },
      error: (e) => { this.ocupado.set(false); this.dialogos.mostrarErro(e, 'Não foi possível registrar a ciência'); },
    });
  }
}
