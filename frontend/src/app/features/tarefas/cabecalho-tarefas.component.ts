// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho comum das telas do Módulo Tarefas (trilha, título e atalhos).

import { Component, computed, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { ItemTrilha, TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';

/** Cabeçalho das tarefas: "Início / Tarefas / Página", título e atalhos (Minhas tarefas, Nova tarefa). */
@Component({
  selector: 'app-cabecalho-tarefas',
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
      <nav aria-label="Atalhos do Módulo Tarefas">
        <a class="acao-secundaria" routerLink="/tarefas" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">Minhas tarefas</a>
        <a class="acao-primaria" routerLink="/tarefas/nova"><span>+</span> Nova tarefa</a>
      </nav>
    </div>
  `,
})
export class CabecalhoTarefasComponent {
  readonly titulo = input.required<string>();
  readonly trilha = input<ItemTrilha[]>([]);
  readonly descricao = input('');
  protected readonly passos = computed<ItemTrilha[]>(() => [{ rotulo: 'Tarefas', rota: '/tarefas' }, ...this.trilha()]);
}
