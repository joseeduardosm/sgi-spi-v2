// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o painel de entrada do Módulo RH: as telas agrupadas por finalidade, com numeração nas sequências reais.

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
  private readonly api = inject(RhApiService);
  protected readonly papeis = signal<PapeisRh | null>(null);
  protected readonly erro = signal(false);
  protected readonly grupos = computed(() => (this.papeis() ? gruposVisiveis(this.papeis()!) : []));

  ngOnInit(): void {
    this.api.papeis().subscribe({ next: (p) => this.papeis.set(p), error: () => this.erro.set(true) });
  }
}
