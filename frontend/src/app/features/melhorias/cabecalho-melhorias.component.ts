// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho do Módulo Melhorias (trilha, título e atalhos "Minhas sugestões" e "Triagem").

import { Component, inject, input, OnInit, signal } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { MelhoriasApiService } from './melhorias-api.service';

@Component({
  selector: 'app-cabecalho-melhorias',
  imports: [RouterLink, RouterLinkActive, TrilhaComponent],
  template: `
    <div class="cabecalho-modulo">
      <div class="cabecalho-pagina" style="margin: 0">
        <div>
          <app-trilha [itens]="[{ rotulo: 'Melhorias', rota: '/melhorias' }]" />
          <h1>{{ titulo() }}</h1>
          @if (descricao()) { <small>{{ descricao() }}</small> }
        </div>
      </div>
      <nav aria-label="Atalhos de melhorias">
        <a class="acao-secundaria" routerLink="/melhorias" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">Minhas sugestões</a>
        @if (triagem()) { <a class="acao-secundaria" routerLink="/melhorias/triagem" routerLinkActive="ativo">Triagem</a> }
      </nav>
    </div>
  `,
})
export class CabecalhoMelhoriasComponent implements OnInit {
  readonly titulo = input.required<string>();
  readonly descricao = input('');
  private readonly api = inject(MelhoriasApiService);
  protected readonly triagem = signal(false);

  ngOnInit(): void {
    this.api.acesso().subscribe({ next: (a) => this.triagem.set(a.triagem), error: () => undefined });
  }
}
