/**
 * =============================================================================
 * ARQUIVO: janela-boas-vindas.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Modal de boas-vindas mostrado no primeiro acesso de quem acabou de ser
 * admitido, com o texto do modelo do RH e um botão que leva ao cadastro.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template inline. Ao iniciar, pergunta à API se há
 * boas-vindas pendentes para o usuário; se houver, mostra o HTML do modelo.
 * Ao clicar em "Completar meu cadastro", confirma a leitura na API (o aviso não
 * volta) e navega para /perfil.
 *
 * FINALIDADE DE NEGÓCIO:
 * Recebe o novo servidor no sistema e o conduz a completar o cadastro, passo
 * necessário para o RH validar os dados. Quem já usava o sistema antes do
 * módulo nunca vê o aviso.
 *
 * CONTEXTO NO SISTEMA:
 * Incluído no layout autenticado. Usa RhAdmissaoApiService (boasVindas e
 * confirmarBoasVindas) e o tipo BoasVindas de rh-admissao.models.ts. O texto é
 * editado em RH > Modelos (modelos.component.ts).
 *
 * =============================================================================
 */

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
  // inject() obtém os serviços pela injeção de dependência do Angular.
  private readonly api = inject(RhAdmissaoApiService);
  private readonly roteador = inject(Router);

  /** Boas-vindas pendentes (null = nada a mostrar); signal() redesenha o modal quando muda. */
  protected readonly aviso = signal<BoasVindas | null>(null);
  protected readonly ocupado = signal(false);

  /** Consulta se há boas-vindas pendentes; erro é ignorado (o modal simplesmente não aparece). */
  ngOnInit(): void {
    this.api.boasVindas().subscribe({ next: (b) => this.aviso.set(b.pendente ? b : null), error: () => undefined });
  }

  /** Registra na API que a pessoa leu as boas-vindas, fecha o modal e vai para o perfil. */
  protected continuar(): void {
    this.ocupado.set(true);
    this.api.confirmarBoasVindas().subscribe({
      next: () => { this.ocupado.set(false); this.aviso.set(null); void this.roteador.navigate(['/perfil']); },
      error: () => this.ocupado.set(false),
    });
  }
}
