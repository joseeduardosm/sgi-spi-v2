// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho das telas de formulário do Módulo Tarefas (trilha, título e descrição).

import { Component, computed, input } from '@angular/core';

import { ItemTrilha, TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';

/** Cabeçalho das telas de formulário: "Tarefas / Página", título e descrição (os atalhos ficam na navegação lateral do módulo). */
@Component({
  selector: 'app-cabecalho-tarefas',
  imports: [TrilhaComponent],
  template: `
    <div class="cabecalho-modulo">
      <div class="cabecalho-pagina" style="margin: 0">
        <div>
          <app-trilha [itens]="passos()" />
          <h1>{{ titulo() }}</h1>
          @if (descricao()) { <small>{{ descricao() }}</small> }
        </div>
      </div>
    </div>
  `,
})
export class CabecalhoTarefasComponent {
  readonly titulo = input.required<string>();
  readonly trilha = input<ItemTrilha[]>([]);
  readonly descricao = input('');
  protected readonly passos = computed<ItemTrilha[]>(() => [{ rotulo: 'Tarefas', rota: '/tarefas' }, ...this.trilha()]);
}
