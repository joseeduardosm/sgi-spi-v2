// Criado por José Eduardo Santana Martins
// Este arquivo serve para dar as boas-vindas no primeiro acesso (modal com o texto do modelo do RH) e levar a pessoa ao cadastro.

import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';

import { RhAdmissaoApiService } from './rh-admissao-api.service';
import { BoasVindas } from './rh-admissao.models';

/**
 * Modal de boas-vindas do primeiro acesso. O texto vem do modelo "Boas-vindas" (RH > Modelos); o mesmo texto já foi enviado por e-mail.
 * Ao confirmar, a pessoa vai para o cadastro (perfil) e o aviso não volta. Quem já usava o sistema antes nunca o vê.
 */
@Component({
  selector: 'app-janela-boas-vindas',
  template: `
    @if (aviso(); as b) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal janela-mensagem" role="alertdialog" aria-modal="true" aria-labelledby="titulo-boas-vindas">
        <header>
          <div><span class="modal-sobretitulo">Primeiro acesso</span><h2 id="titulo-boas-vindas">{{ b.titulo }}</h2></div>
        </header>
        <div class="corpo-janela-mensagem" [innerHTML]="b.html"></div>
        <footer>
          <button type="button" class="acao-primaria" [class.carregando]="ocupado()" [disabled]="ocupado()" (click)="continuar()">Completar meu cadastro</button>
        </footer>
      </section>
    }
  `,
})
export class JanelaBoasVindasComponent implements OnInit {
  private readonly api = inject(RhAdmissaoApiService);
  private readonly roteador = inject(Router);

  protected readonly aviso = signal<BoasVindas | null>(null);
  protected readonly ocupado = signal(false);

  ngOnInit(): void {
    this.api.boasVindas().subscribe({ next: (b) => this.aviso.set(b.pendente ? b : null), error: () => undefined });
  }

  protected continuar(): void {
    this.ocupado.set(true);
    this.api.confirmarBoasVindas().subscribe({
      next: () => { this.ocupado.set(false); this.aviso.set(null); void this.roteador.navigate(['/perfil']); },
      error: () => this.ocupado.set(false),
    });
  }
}
