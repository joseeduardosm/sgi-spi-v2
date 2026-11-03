// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho do plano de face da rede (trilha, título e atalhos conforme o papel da pessoa).

import { Component, inject, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';

@Component({
  selector: 'app-cabecalho-rede',
  imports: [RouterLink, RouterLinkActive, TrilhaComponent],
  template: `
    <div class="cabecalho-modulo">
      <div class="cabecalho-pagina" style="margin: 0">
        <div>
          <app-trilha [itens]="[{ rotulo: 'Rede', rota: '/rede' }]" />
          <h1>{{ titulo() }}</h1>
          @if (descricao()) { <small>{{ descricao() }}</small> }
        </div>
      </div>
      <nav aria-label="Atalhos da rede">
        <a class="acao-secundaria" routerLink="/rede" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">Equipamentos</a>
        <a class="acao-secundaria" routerLink="/rede/topologia" routerLinkActive="ativo">Topologia</a>
        <a class="acao-secundaria" routerLink="/rede/cadastros" routerLinkActive="ativo">Pontos, VLANs e modelos</a>
      </nav>
    </div>
  `,
})
export class CabecalhoRedeComponent {
  readonly titulo = input.required<string>();
  readonly descricao = input('');
  protected readonly papeis = inject(AcessoService).rede;
}
