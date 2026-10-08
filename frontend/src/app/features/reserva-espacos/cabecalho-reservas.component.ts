// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho da Reserva de Espaços (trilha, título e atalhos conforme o papel do usuário).

import { Component, inject, input, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { EstadoReservasService } from './estado-reservas.service';

@Component({
  selector: 'app-cabecalho-reservas',
  imports: [RouterLink, RouterLinkActive, TrilhaComponent],
  template: `
    <div class="cabecalho-modulo">
      <div class="cabecalho-pagina" style="margin: 0">
        <div>
          <app-trilha [itens]="[{ rotulo: 'Reserva de Espaços', rota: '/reserva-espacos' }]" />
          <h1>{{ titulo() }}</h1>
          @if (descricao()) { <small>{{ descricao() }}</small> }
        </div>
      </div>
      <nav aria-label="Atalhos da Reserva de Espaços">
        <a class="acao-secundaria" routerLink="/reserva-espacos" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">Agenda</a>
        <a class="acao-secundaria" routerLink="/reserva-espacos/minhas" routerLinkActive="ativo">Minhas reservas</a>
        <a class="acao-primaria" routerLink="/reserva-espacos/nova">Nova reserva</a>
        @if (estado.ehFiscal()) {
          <a class="acao-secundaria" routerLink="/reserva-espacos/fila" routerLinkActive="ativo">Fila do fiscal</a>
          <a class="acao-secundaria" routerLink="/reserva-espacos/reservas" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">Todas</a>
          <a class="acao-secundaria" routerLink="/reserva-espacos/espacos" routerLinkActive="ativo">Espaços</a>
          <a class="acao-secundaria" routerLink="/reserva-espacos/painel" routerLinkActive="ativo">Painel</a>
          <a class="acao-secundaria" routerLink="/reserva-espacos/configuracao" routerLinkActive="ativo">Configuração</a>
        }
      </nav>
    </div>
  `,
})
export class CabecalhoReservasComponent implements OnInit {
  readonly titulo = input.required<string>();
  readonly descricao = input('');
  protected readonly estado = inject(EstadoReservasService);

  ngOnInit(): void {
    this.estado.carregar().subscribe();
  }
}
