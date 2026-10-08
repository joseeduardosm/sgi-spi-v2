// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de um livro dos Manuais (sumário com capítulos e páginas).

import { Component, effect, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { DetalheLivro, ManuaisService } from '../../core/manuais/manuais.service';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { erroExibivel } from '../../shared/utilitarios/erros-api';

/** Sumário do livro: capítulos (com as páginas) e páginas soltas, na ordem do BookStack. */
@Component({
  selector: 'app-livro-manual',
  imports: [RouterLink, TrilhaComponent],
  template: `
    @if (livro(); as l) {
      <div class="cabecalho-pagina">
        <div>
          <app-trilha [itens]="[{ rotulo: 'Manuais', rota: '/manuais' }, { rotulo: l.nome }]" />
          <h1>{{ l.nome }}</h1>
          @if (l.descricao) { <small>{{ l.descricao }}</small> }
        </div>
        <div class="acoes-formulario">
          @if (l.primeira_pagina_id) { <a class="acao-primaria" [routerLink]="['/manuais/paginas', l.primeira_pagina_id]">Começar a ler</a> }
          <a class="acao-secundaria" [href]="l.url_origem" target="_blank" rel="noopener">Abrir no BookStack ↗</a>
        </div>
      </div>
      <section class="painel-gestao manuais-painel" aria-label="Sumário">
        <ul class="manuais-sumario">
          @for (item of l.sumario; track item.tipo + item.id) {
            @if (item.tipo === 'capitulo') {
              <li><strong>{{ item.nome }}</strong>
                <ul>@for (p of item.paginas; track p.id) { <li><a [routerLink]="['/manuais/paginas', p.id]">{{ p.nome }}</a></li> }</ul>
              </li>
            } @else {
              <li><a [routerLink]="['/manuais/paginas', item.id]">{{ item.nome }}</a></li>
            }
          } @empty { <li class="estado-vazio">Este livro ainda não tem páginas.</li> }
        </ul>
      </section>
    } @else if (erro()) {
      <p class="aviso-admin erro" role="alert">{{ erro() }}</p>
    } @else {
      <p class="estado-vazio">Carregando…</p>
    }
  `,
})
export class LivroComponent {
  private readonly api = inject(ManuaisService);

  /** Id do livro (parâmetro da rota). */
  readonly id = input.required<string>();
  protected readonly livro = signal<DetalheLivro | null>(null);
  protected readonly erro = signal('');

  constructor() {
    effect(() => {
      const id = Number(this.id());
      this.livro.set(null);
      this.erro.set('');
      this.api.livro(id).subscribe({ next: (l) => this.livro.set(l), error: (e) => this.erro.set(erroExibivel(e).mensagem) });
    });
  }
}
