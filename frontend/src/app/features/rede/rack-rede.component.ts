// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar um rack com os equipamentos na posição (U) de cada um; clicar no equipamento abre a face dele.

import { Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EquipamentoResumo, Rack, ROTULOS_TIPO_EQUIPAMENTO } from './rede.models';

@Component({
  selector: 'app-rack-rede',
  imports: [RouterLink],
  styleUrl: './rack-rede.component.scss',
  template: `
    <section class="rack" [attr.data-cor]="rack().cor" [attr.aria-label]="'Rack ' + rack().nome">
      <header><div><h2>{{ rack().nome }}</h2><small>{{ rack().sala || 'Sem sala' }} · {{ rack().altura_u }}U · {{ equipamentos().length }} equipamento(s)</small></div></header>
      <div class="rack-corpo" [style.grid-template-rows]="'repeat(' + altura() + ', var(--altura-u))'">
        <!-- Numeração dos U: de cima (o maior) para baixo (U1) -->
        @for (u of us(); track u; let i = $index) {
          <span class="rack-u" [style.grid-row]="i + 1" aria-hidden="true">{{ u }}</span>
        }
        @for (e of posicionados(); track e.id) {
          <a class="rack-equipamento" [routerLink]="['/rede/equipamentos', e.id]" [style.grid-row]="linha(e)"
            [attr.aria-label]="e.nome + ', ' + tipo(e) + ', U' + e.posicao_u + ': ' + e.portas_up + ' portas ligadas e ' + e.portas_down + ' desligadas'">
            <strong>{{ e.nome }}</strong>
            <small>{{ tipo(e) }}</small>
            @if (e.portas_total) {
              <span class="rack-portas" aria-hidden="true">
                @if (e.portas_up) { <span class="ponto-estado" data-estado="up"></span>{{ e.portas_up }} }
                @if (e.portas_down) { <span class="ponto-estado" data-estado="down"></span>{{ e.portas_down }} }
              </span>
            }
          </a>
        }
      </div>
      <!-- Ações de quem administra (Editar, Excluir), vindas da tela -->
      <footer class="rack-acoes"><ng-content /></footer>
      @if (semPosicao().length) {
        <p class="rack-sem-posicao">Sem posição no rack:
          @for (e of semPosicao(); track e.id) { <a [routerLink]="['/rede/equipamentos', e.id]">{{ e.nome }}</a>{{ $last ? '' : ', ' }} }</p>
      }
    </section>
  `,
})
export class RackRedeComponent {
  readonly rack = input.required<Rack>();
  readonly equipamentos = input.required<EquipamentoResumo[]>();

  protected readonly posicionados = computed(() => this.equipamentos().filter((e) => e.posicao_u));
  protected readonly semPosicao = computed(() => this.equipamentos().filter((e) => !e.posicao_u));
  /** A altura do cadastro do rack (ou até o U mais alto ocupado, se algum passar). */
  protected readonly altura = computed(() => Math.max(this.rack().altura_u, ...this.posicionados().map((e) => (e.posicao_u ?? 1) + Math.max(1, e.altura_u) - 1)));
  protected readonly us = computed(() => Array.from({ length: this.altura() }, (_, i) => this.altura() - i));

  /** Linha da grade (1 = topo): o equipamento na posição U ocupa de U até U + altura - 1. */
  protected linha(e: EquipamentoResumo): string {
    const altura = Math.max(1, e.altura_u);
    const topo = (e.posicao_u ?? 1) + altura - 1;
    return `${this.altura() - topo + 1} / span ${altura}`;
  }

  protected tipo(e: EquipamentoResumo): string {
    return ROTULOS_TIPO_EQUIPAMENTO[e.tipo];
  }
}
