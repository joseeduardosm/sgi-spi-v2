// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho do Módulo Protocolo (trilha, título e atalhos Numeração, Painel e Administração).

import { Component, inject, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';

@Component({
  selector: 'app-cabecalho-protocolo',
  imports: [RouterLink, RouterLinkActive, TrilhaComponent],
  template: `
    <div class="cabecalho-modulo">
      <div class="cabecalho-pagina" style="margin: 0">
        <div>
          <app-trilha [itens]="[{ rotulo: 'Protocolo', rota: '/protocolo' }]" />
          <h1>{{ titulo() }}</h1>
          @if (descricao()) { <small>{{ descricao() }}</small> }
        </div>
      </div>
      <nav aria-label="Atalhos do Protocolo">
        <a class="acao-secundaria" routerLink="/protocolo" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">Numeração</a>
        <a class="acao-secundaria" routerLink="/protocolo/painel" routerLinkActive="ativo">Painel</a>
        @if (administra()) { <a class="acao-secundaria" routerLink="/protocolo/administracao" routerLinkActive="ativo">Administração</a> }
      </nav>
    </div>
  `,
})
export class CabecalhoProtocoloComponent {
  readonly titulo = input.required<string>();
  readonly descricao = input('');
  private readonly acesso = inject(AcessoService);
  protected readonly administra = () => this.acesso.pode('protocolo', 'CONTROLE_TOTAL');
}
