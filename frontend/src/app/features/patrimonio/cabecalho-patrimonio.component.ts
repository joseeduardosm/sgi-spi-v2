// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho do módulo Patrimônio (trilha, título, atalhos e aviso de itens aguardando envio).
import { Component, inject, input, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { FilaOfflineService } from './fila-offline.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';

@Component({
  selector: 'app-cabecalho-patrimonio',
  imports: [RouterLink, RouterLinkActive, TrilhaComponent],
  template: `
    <div class="cabecalho-modulo">
      <div class="cabecalho-pagina" style="margin: 0">
        <div>
          <app-trilha [itens]="[{ rotulo: 'Patrimônio', rota: '/patrimonio' }]" />
          <h1>{{ titulo() }}</h1>
          @if (descricao()) { <small>{{ descricao() }}</small> }
        </div>
      </div>
      <nav aria-label="Atalhos do Patrimônio" class="pat-atalhos">
        <a class="acao-secundaria" routerLink="/patrimonio" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">Bens</a>
        <a class="acao-secundaria" routerLink="/patrimonio/movimentacoes" routerLinkActive="ativo">Movimentações</a>
        <a class="acao-secundaria" routerLink="/patrimonio/inserviveis" routerLinkActive="ativo">Inservíveis</a>
        <a class="acao-secundaria" routerLink="/patrimonio/extraviados" routerLinkActive="ativo">Extraviados</a>
        <a class="acao-secundaria" routerLink="/patrimonio/baixas" routerLinkActive="ativo">Baixa</a>
        <a class="acao-secundaria" routerLink="/patrimonio/painel" routerLinkActive="ativo">Painel</a>
        <a class="acao-secundaria" routerLink="/patrimonio/localizacoes" routerLinkActive="ativo">Locais</a>
        @if (estado.podeAdministrar()) { <a class="acao-secundaria" routerLink="/patrimonio/parametros" routerLinkActive="ativo">Parâmetros</a> }
      </nav>
    </div>
    @if (!fila.online() || fila.itens().length) {
      <div class="pat-aviso-conexao" role="status">
        @if (!fila.online()) { <strong>Sem conexão.</strong> O que você fizer fica guardado no aparelho e é enviado quando o sinal voltar. }
        @if (fila.itens().length) {
          <span>{{ fila.itens().length }} item(ns) aguardando envio.</span>
          <a href="javascript:void(0)" (click)="$event.preventDefault(); fila.sincronizar()">Enviar agora</a>
          <a routerLink="/patrimonio/pendencias">Ver</a>
        }
      </div>
    }
  `,
})
export class CabecalhoPatrimonioComponent implements OnInit {
  readonly titulo = input.required<string>();
  readonly descricao = input('');
  protected readonly estado = inject(PatrimonioEstadoService);
  protected readonly fila = inject(FilaOfflineService);

  ngOnInit(): void {
    void this.estado.carregar();
  }
}
