/**
 * =============================================================================
 * ARQUIVO: inicio-rh.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Painel de entrada do Módulo RH (/rh): mostra as telas agrupadas por
 * finalidade, com numeração nos grupos que são sequências de trabalho.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template inline. Busca os papéis do usuário no
 * RH (RhApiService.papeis) e, com eles, filtra os grupos e telas visíveis pela
 * função gruposVisiveis de menu-rh.ts. Mostra esqueleto enquanto carrega e
 * mensagem de erro se a API falhar.
 *
 * FINALIDADE DE NEGÓCIO:
 * Orienta quem usa o RH a achar a tela certa e a seguir a ordem real dos
 * processos (ex.: pré-cadastro, admissão), mostrando a cada pessoa só o que o
 * papel dela permite (servidor, autorizador, CGP).
 *
 * CONTEXTO NO SISTEMA:
 * Rota raiz do Módulo RH em rh.routes.ts. A definição dos grupos fica em
 * menu-rh.ts, compartilhada com a sub-navegação do app-cabecalho-rh.
 *
 * =============================================================================
 */

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { gruposVisiveis } from './menu-rh';
import { RhApiService } from './rh-api.service';
import { PapeisRh } from './rh.models';

/** Entrada do RH (`/rh`): um cartão por grupo; os grupos numerados mostram a ordem em que o trabalho é feito. */
@Component({
  selector: 'app-inicio-rh',
  imports: [RouterLink, TrilhaComponent, EsqueletoComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'RH' }]" />
        <h1>Recursos Humanos</h1>
        <small>Escolha o que deseja fazer. Nos grupos numerados, siga a ordem dos passos.</small>
      </div>
    </div>

    @if (papeis(); as p) {
      <div class="rh-grupos">
        @for (g of grupos(); track g.id) {
          <section class="rh-grupo" [attr.aria-labelledby]="'rh-grupo-' + g.id">
            <h2 id="rh-grupo-{{ g.id }}">{{ g.titulo }}</h2>
            <p class="rh-grupo-descricao">{{ g.descricao }}</p>
            <ul>
              @for (t of g.telas; track t.rota; let i = $index) {
                <li>
                  <a [routerLink]="t.rota">
                    @if (g.numerado) { <span class="rh-grupo-numero" aria-hidden="true">{{ i + 1 }}</span> }
                    <span class="rh-grupo-texto"><strong>{{ t.rotulo }}</strong><small>{{ t.descricao }}</small></span>
                  </a>
                </li>
              }
            </ul>
          </section>
        }
      </div>
    } @else if (erro()) {
      <p class="estado-vazio">Não foi possível carregar o menu do RH. Atualize a página.</p>
    } @else {
      <app-esqueleto tipo="cartao" />
    }
  `,
})
export class InicioRhComponent implements OnInit {
  // inject() obtém o serviço pela injeção de dependência do Angular.
  private readonly api = inject(RhApiService);
  // signal(): estado reativo (papéis do usuário e falha na carga).
  protected readonly papeis = signal<PapeisRh | null>(null);
  protected readonly erro = signal(false);
  /** Grupos que o usuário pode ver; computed() recalcula sozinho quando papeis muda. */
  protected readonly grupos = computed(() => (this.papeis() ? gruposVisiveis(this.papeis()!) : []));

  /** Carrega os papéis do usuário no RH; sem eles não dá para decidir que telas mostrar. */
  ngOnInit(): void {
    this.api.papeis().subscribe({ next: (p) => this.papeis.set(p), error: () => this.erro.set(true) });
  }
}
