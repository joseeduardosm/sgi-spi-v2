// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho do módulo Chamados (trilha, título e atalhos conforme o papel da pessoa).

import { Component, inject, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';

@Component({
  selector: 'app-cabecalho-chamados',
  imports: [RouterLink, RouterLinkActive, TrilhaComponent],
  template: `
    <div class="cabecalho-modulo">
      <div class="cabecalho-pagina" style="margin: 0">
        <div>
          <app-trilha [itens]="[{ rotulo: 'Chamados', rota: '/chamados' }]" />
          <h1>{{ titulo() }}</h1>
          @if (descricao()) { <small>{{ descricao() }}</small> }
        </div>
      </div>
      <nav aria-label="Atalhos dos Chamados">
        @if (papeis()?.abrir) {
          <a class="acao-secundaria" routerLink="/chamados/meus" routerLinkActive="ativo">Meus chamados</a>
        }
        @if (papeis()?.abrir) {
          <a class="acao-secundaria" routerLink="/chamados/aprovacoes" routerLinkActive="ativo">Minhas aprovações</a>
        }
        @if (papeis()?.atender) {
          <a class="acao-secundaria" routerLink="/chamados/fila" routerLinkActive="ativo">Fila de atendimento</a>
          <a class="acao-secundaria" routerLink="/chamados/relatorios" routerLinkActive="ativo">Relatórios</a>
        }
        <!-- Painel: de todos, mostra os chamados em que o setor da pessoa é o responsável -->
        <a class="acao-secundaria" routerLink="/chamados/painel" routerLinkActive="ativo">Painel</a>
        @if (papeis()?.administrar) {
          <a class="acao-secundaria" routerLink="/chamados/parametros" routerLinkActive="ativo">Parâmetros</a>
        }
        @if (papeis()?.abrir) {
          <a class="acao-primaria" routerLink="/chamados" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">Abrir chamado</a>
        }
      </nav>
    </div>
  `,
})
export class CabecalhoChamadosComponent {
  readonly titulo = input.required<string>();
  readonly descricao = input('');
  // Os papéis já vêm carregados pela guarda da rota (GET /chamados/contexto)
  protected readonly papeis = inject(AcessoService).chamados;
}
