// Criado por José Eduardo Santana Martins
// Este arquivo serve para a casca do Módulo Tarefas: navegação lateral própria (Minhas tarefas, validações e equipes) e a área das telas.

import { Component, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { EstadoTarefasService } from './estado-tarefas.service';

/** Preferência (navegador) da navegação lateral recolhida. */
const CHAVE_RECOLHIDA = 'tarefas.navegacao.recolhida';

/**
 * Layout do módulo, como os "espaços" do Trello/ClickUp: à esquerda, Minhas tarefas, as entregas
 * para validar e a árvore de equipes (quadros); à direita, a tela escolhida. A barra lateral do
 * sistema continua com um só item "Tarefas"; esta navegação é interna ao módulo.
 */
@Component({
  selector: 'app-modulo-tarefas',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="modulo-tarefas" [class.recolhida]="recolhida()">
      <nav class="navegacao-tarefas" aria-label="Navegação do Módulo Tarefas">
        <div class="topo-navegacao">
          @if (!recolhida()) { <strong>Tarefas</strong> }
          <button type="button" class="botao-icone" [attr.aria-label]="recolhida() ? 'Expandir a navegação' : 'Recolher a navegação'"
                  [attr.aria-expanded]="!recolhida()" (click)="alternar()">{{ recolhida() ? '»' : '«' }}</button>
        </div>
        @if (!recolhida()) {
          <a class="acao-primaria nova-tarefa-navegacao" routerLink="/tarefas/nova"><span aria-hidden="true">+</span> Nova tarefa</a>

          <a class="item-navegacao" routerLink="/tarefas" routerLinkActive="ativo" [routerLinkActiveOptions]="{ exact: true }">
            <span class="icone-navegacao" aria-hidden="true">★</span> Minhas tarefas</a>
          @if (estado.paraValidar(); as n) {
            <a class="item-navegacao" [routerLink]="rotaValidar()" [queryParams]="{ recorte: 'validacao' }">
              <span class="icone-navegacao" aria-hidden="true">◷</span> Para validar <span class="contagem-navegacao alerta">{{ n }}</span></a>
          }

          <div class="secao-navegacao">
            <span>Equipes</span>
            <a routerLink="/tarefas/equipes" title="Visão geral das equipes">ver todas</a>
          </div>
          @for (item of estado.arvore(); track item.equipe.id) {
            <a class="item-navegacao equipe-navegacao" [style.padding-left.px]="14 + item.nivel * 14"
               [routerLink]="['/tarefas/equipes', item.equipe.id]" routerLinkActive="ativo" [title]="item.equipe.nome">
              <span class="ponto-equipe" aria-hidden="true"></span>
              <span class="nome-navegacao">{{ item.equipe.nome }}</span>
              @if (item.equipe.lider && item.equipe.indicadores.em_validacao) {
                <span class="contagem-navegacao alerta" title="Entregas para validar">{{ item.equipe.indicadores.em_validacao }}</span>
              }
              <span class="contagem-navegacao" title="Tarefas em aberto">{{ item.equipe.indicadores.operacionais }}</span>
            </a>
          } @empty { <p class="vazio-navegacao">Você ainda não está em nenhuma equipe.</p> }
          <a class="item-navegacao discreto" routerLink="/tarefas/equipes/nova/configurar">+ Nova equipe</a>
        }
      </nav>
      <main class="area-tarefas"><router-outlet /></main>
    </div>
  `,
})
export class ModuloTarefasComponent implements OnInit {
  protected readonly estado = inject(EstadoTarefasService);
  private readonly roteador = inject(Router);
  protected readonly recolhida = signal(lerRecolhida());

  constructor() {
    // A cada troca de tela dentro do módulo, as contagens das equipes são atualizadas.
    // Mudanças só nos filtros (query string) não recarregam.
    let caminhoAnterior = this.caminho(this.roteador.url);
    this.roteador.events.pipe(filter((e) => e instanceof NavigationEnd), takeUntilDestroyed()).subscribe((e) => {
      const caminho = this.caminho((e as NavigationEnd).urlAfterRedirects);
      if (caminho !== caminhoAnterior) this.estado.recarregar();
      caminhoAnterior = caminho;
    });
  }

  /** URL sem a query string ("/tarefas/equipes/abc?visao=lista" → "/tarefas/equipes/abc"). */
  private caminho(url: string): string {
    return url.split('?')[0];
  }

  ngOnInit(): void {
    this.estado.recarregar();
  }

  /** "Para validar": a primeira equipe liderada com entregas pendentes (a lista já abre filtrada). */
  protected rotaValidar(): string[] {
    const equipe = this.estado.equipes().find((e) => e.lider && e.indicadores.em_validacao);
    return equipe ? ['/tarefas/equipes', equipe.id] : ['/tarefas'];
  }

  protected alternar(): void {
    this.recolhida.update((v) => !v);
    try {
      localStorage.setItem(CHAVE_RECOLHIDA, this.recolhida() ? '1' : '0');
    } catch {
      // Sem armazenamento disponível: a preferência vale só nesta visita
    }
  }
}

function lerRecolhida(): boolean {
  try {
    return localStorage.getItem(CHAVE_RECOLHIDA) === '1';
  } catch {
    return false;
  }
}
