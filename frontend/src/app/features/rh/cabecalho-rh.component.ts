// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho comum das telas do Módulo RH (trilha, título e atalhos por papel).

import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { ItemTrilha, TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { RhApiService } from './rh-api.service';
import { PapeisRh } from './rh.models';

/** Cabeçalho do RH: atalhos Férias e LP e Feriados (todos), Painel (CGP e autorizadores), Validações e Parâmetros (CGP). */
@Component({
  selector: 'app-cabecalho-rh',
  imports: [RouterLink, RouterLinkActive, TrilhaComponent],
  template: `
    <div class="cabecalho-modulo">
      <div class="cabecalho-pagina" style="margin: 0">
        <div>
          <app-trilha [itens]="passos()" />
          <h1>{{ titulo() }}</h1>
          @if (descricao()) { <small>{{ descricao() }}</small> }
        </div>
      </div>
      <nav aria-label="Atalhos do Módulo RH">
        <a class="acao-secundaria" routerLink="/rh/ferias" routerLinkActive="ativo">Férias e LP</a>
        <a class="acao-secundaria" routerLink="/rh/feriados" routerLinkActive="ativo">Feriados</a>
        @if (papeis()?.cgp || papeis()?.autorizador) { <a class="acao-secundaria" routerLink="/rh/painel-afastamentos" routerLinkActive="ativo">Painel</a> }
        @if (papeis()?.cgp) {
          <a class="acao-secundaria" routerLink="/rh/validacoes" routerLinkActive="ativo">Validações</a>
          <a class="acao-secundaria" routerLink="/rh/parametros" routerLinkActive="ativo">Parâmetros</a>
        }
      </nav>
    </div>
  `,
})
export class CabecalhoRhComponent implements OnInit {
  readonly titulo = input.required<string>();
  readonly trilha = input<string[]>([]);
  readonly descricao = input('');
  private readonly api = inject(RhApiService);
  protected readonly papeis = signal<PapeisRh | null>(null);
  /** "Início / RH / Página": RH leva às férias (entrada do módulo); a página, a ela mesma. */
  protected readonly passos = computed<ItemTrilha[]>(() => [{ rotulo: 'RH', rota: '/rh/ferias' }, ...this.trilha().map((rotulo) => ({ rotulo }))]);

  ngOnInit(): void {
    this.api.papeis().subscribe({ next: (p) => this.papeis.set(p), error: () => undefined });
  }
}
