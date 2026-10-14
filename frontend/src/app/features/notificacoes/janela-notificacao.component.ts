// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar em janela os avisos marcados para isso (ex.: designação na equipe de um contrato).

import { Component, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { CaixaNotificacoesService } from '../../core/notificacoes/caixa-notificacoes.service';
import { NotificacoesApiService } from '../../core/notificacoes/notificacoes-api.service';
import { ROTULOS_CATEGORIA } from '../../core/notificacoes/notificacoes.models';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';

/**
 * Janela de aviso (não bloqueia nada): ao aparecer, a notificação conta como lida; "Ciente" registra a
 * ciência e "Abrir" leva ao link. Fechar (×, Esc ou fundo) só esconde; a notificação continua na caixa.
 */
@Component({
  selector: 'app-janela-notificacao',
  imports: [LinkificarPipe],
  host: { '(document:keydown.escape)': 'fechar()' },
  template: `
    @if (caixa.janela(); as m) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal janela-mensagem" role="dialog" aria-modal="true" aria-labelledby="titulo-janela-mensagem">
        <header>
          <div><span class="modal-sobretitulo">{{ categorias[m.categoria] }} · {{ m.autor_nome }}</span>
            <h2 id="titulo-janela-mensagem">{{ m.assunto }}</h2></div>
          <button type="button" aria-label="Fechar" (click)="fechar()">×</button>
        </header>
        <div class="corpo-janela-mensagem" [innerHTML]="m.corpo | linkificar"></div>
        <footer>
          @if (m.link) { <button type="button" class="acao-secundaria" [disabled]="ocupado()" (click)="abrirLink(m.link)">Abrir</button> }
          <button type="button" class="acao-primaria" [disabled]="ocupado()" (click)="ciente(m.id)">Ciente</button>
        </footer>
      </section>
    }
  `,
})
export class JanelaNotificacaoComponent {
  protected readonly caixa = inject(CaixaNotificacoesService);
  private readonly api = inject(NotificacoesApiService);
  private readonly roteador = inject(Router);
  protected readonly categorias = ROTULOS_CATEGORIA;
  protected readonly ocupado = signal(false);

  constructor() {
    // A janela conta como lida assim que aparece (não abre de novo depois)
    effect(() => {
      const m = this.caixa.janela();
      if (m && !m.visualizada_em) this.api.abrir(m.id).subscribe({ error: () => undefined });
    });
  }

  protected fechar(): void {
    if (!this.caixa.janela()) return;
    this.caixa.janela.set(null);
    this.caixa.atualizar();
  }

  protected ciente(id: string): void {
    this.ocupado.set(true);
    this.api.ciencia(id).subscribe({
      next: () => {
        this.ocupado.set(false);
        this.fechar();
      },
      error: () => {
        this.ocupado.set(false);
        this.fechar();
      },
    });
  }

  protected abrirLink(link: string): void {
    this.fechar();
    void this.roteador.navigateByUrl(link);
  }
}
