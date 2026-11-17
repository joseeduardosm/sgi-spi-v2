/**
 * =============================================================================
 * ARQUIVO: rack-rede.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Desenhar um rack com os equipamentos na posição (U) de cada um. Na visão
 * Racks, clicar no equipamento abre a face dele; no cadastro do equipamento
 * (modo "escolha"), os U livres ficam clicáveis para escolher a posição.
 *
 * RESUMO TÉCNICO:
 * Componente standalone. A grade tem uma linha por U (U1 embaixo). Com
 * `escolha = true`: os equipamentos viram blocos sem link (para não sair do
 * formulário), cada U livre vira um rótulo com radio escondido e o novo
 * equipamento aparece no U escolhido, com a altura do modelo (`alturaNova`).
 * U livre onde o equipamento não cabe inteiro fica desativado, com o motivo.
 * O clique emite `pedirU`; quem usa confirma (Sim/Não) e devolve o U em
 * `uEscolhido`. O radio não marca sozinho (preventDefault): só a confirmação
 * marca.
 *
 * FINALIDADE DE NEGÓCIO:
 * Pedido do usuário (17/11/2026): ao escolher o rack no cadastro, ver o rack
 * com o que já está montado nele e escolher o U clicando num espaço livre.
 *
 * CONTEXTO NO SISTEMA:
 * Visão Racks (equipamentos-rede.component.ts) e cadastro do equipamento
 * (cadastro-equipamento-rede.component.ts).
 *
 * =============================================================================
 */

import { Component, computed, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EquipamentoResumo, Rack, ROTULOS_TIPO_EQUIPAMENTO } from './rede.models';

/** U livre no modo escolha: se o equipamento novo cabe inteiro a partir dele (e, se não, por quê). */
interface ULivre { u: number; cabe: boolean; motivo: string }

/** Recursos do Angular: `input()` = entrada do pai (lida como função), `output()` = evento para o pai, `computed()` = valor recalculado sozinho. */
@Component({
  selector: 'app-rack-rede',
  imports: [RouterLink],
  styleUrl: './rack-rede.component.scss',
  template: `
    <section class="rack" [attr.data-cor]="rack().cor" [attr.aria-label]="'Rack ' + rack().nome">
      <header><div><h2>{{ rack().nome }}</h2><small>{{ rack().sala || 'Sem sala' }} · {{ rack().altura_u }}U · {{ ocupantes().length }} equipamento(s)</small></div></header>
      <div class="rack-corpo" [style.grid-template-rows]="'repeat(' + altura() + ', var(--altura-u))'"
        [attr.role]="escolha() ? 'radiogroup' : null" [attr.aria-label]="escolha() ? 'Posição (U) no rack ' + rack().nome : null">
        <!-- Numeração dos U: de cima (o maior) para baixo (U1) -->
        @for (u of us(); track u; let i = $index) {
          <span class="rack-u" [style.grid-row]="i + 1" aria-hidden="true">{{ u }}</span>
        }
        @for (e of posicionados(); track e.id) {
          @if (escolha()) {
            <!-- No cadastro, o equipamento é só um bloco ocupado (sem link, para não sair do formulário) -->
            <div class="rack-equipamento ocupado" [style.grid-row]="linha(e.posicao_u!, e.altura_u)" [attr.aria-label]="e.nome + ', ocupa a partir do U' + e.posicao_u">
              <strong>{{ e.nome }}</strong><small>{{ tipo(e) }}</small>
            </div>
          } @else {
            <a class="rack-equipamento" [routerLink]="['/rede/equipamentos', e.id]" [style.grid-row]="linha(e.posicao_u!, e.altura_u)"
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
        }
        @if (escolha()) {
          @for (l of livres(); track l.u) {
            <label class="rack-livre" [class.nao-cabe]="!l.cabe" [style.grid-row]="linha(l.u, 1)" [title]="l.motivo">
              <input type="radio" [name]="'rack-u-' + rack().id" [value]="l.u" [checked]="false" [disabled]="!l.cabe"
                [attr.aria-label]="'U' + l.u + (l.cabe ? ' livre' : ': ' + l.motivo)" (click)="$event.preventDefault(); pedirU.emit(l.u)" />
              <span>U{{ l.u }} · {{ l.cabe ? 'livre' : 'não cabe (o equipamento ocupa ' + alturaNova() + 'U)' }}</span>
              @if (l.cabe) { <small aria-hidden="true">Clique para colocar aqui</small> }
            </label>
          }
          @if (uEscolhido(); as u) {
            <!-- O equipamento novo no U escolhido, com a altura do modelo -->
            <div class="rack-equipamento novo" [style.grid-row]="linha(u, alturaNova())" aria-live="polite">
              <strong>{{ nomeNovo() || 'Este equipamento' }}</strong><small>U{{ u }}{{ alturaNova() > 1 ? ' a U' + (u + alturaNova() - 1) : '' }}</small>
            </div>
          }
        }
      </div>
      <!-- Ações de quem administra (Editar, Excluir), vindas da tela -->
      <footer class="rack-acoes"><ng-content /></footer>
      @if (semPosicao().length) {
        <p class="rack-sem-posicao">Sem posição no rack:
          @for (e of semPosicao(); track e.id) {
            @if (escolha()) { {{ e.nome }} } @else { <a [routerLink]="['/rede/equipamentos', e.id]">{{ e.nome }}</a> }{{ $last ? '' : ', ' }}
          }</p>
      }
    </section>
  `,
})
export class RackRedeComponent {
  readonly rack = input.required<Rack>();
  readonly equipamentos = input.required<EquipamentoResumo[]>();
  /** Modo escolha (cadastro do equipamento): U livres clicáveis. */
  readonly escolha = input(false);
  /** Quantos U o equipamento novo ocupa (do modelo de face). */
  readonly alturaNova = input(1);
  /** U já escolhido (confirmado), para desenhar o equipamento novo nele. */
  readonly uEscolhido = input<number | null>(null);
  readonly nomeNovo = input('');
  /** Na edição: o próprio equipamento não conta como ocupante (pode mudar de U). */
  readonly ignorarId = input<string | null>(null);
  /** Clicou num U livre onde o equipamento cabe: quem usa pergunta Sim/Não e, se sim, devolve em `uEscolhido`. */
  readonly pedirU = output<number>();

  /** Os equipamentos do rack que contam (sem o próprio, na edição). */
  protected readonly ocupantes = computed(() => this.equipamentos().filter((e) => e.id !== this.ignorarId()));
  protected readonly posicionados = computed(() => this.ocupantes().filter((e) => e.posicao_u));
  protected readonly semPosicao = computed(() => this.ocupantes().filter((e) => !e.posicao_u));
  /** A altura do cadastro do rack (ou até o U mais alto ocupado, se algum passar). */
  protected readonly altura = computed(() => Math.max(this.rack().altura_u, ...this.posicionados().map((e) => (e.posicao_u ?? 1) + Math.max(1, e.altura_u) - 1)));
  protected readonly us = computed(() => Array.from({ length: this.altura() }, (_, i) => this.altura() - i));

  /** U ocupados pelos equipamentos (cada um do U dele até U + altura - 1). */
  private readonly ocupados = computed(() => {
    const conjunto = new Set<number>();
    for (const e of this.posicionados()) for (let u = e.posicao_u!; u < e.posicao_u! + Math.max(1, e.altura_u); u++) conjunto.add(u);
    return conjunto;
  });

  /** U livres do rack (fora o trecho do equipamento novo já escolhido) e se o equipamento novo cabe inteiro a partir de cada um. */
  protected readonly livres = computed<ULivre[]>(() => {
    const altura = Math.max(1, this.alturaNova());
    const escolhido = this.uEscolhido();
    const lista: ULivre[] = [];
    for (let u = 1; u <= this.rack().altura_u; u++) {
      if (this.ocupados().has(u) || (escolhido !== null && u >= escolhido && u < escolhido + altura)) continue;
      let cabe = u + altura - 1 <= this.rack().altura_u;
      for (let x = u; cabe && x < u + altura; x++) if (this.ocupados().has(x)) cabe = false;
      lista.push({ u, cabe, motivo: cabe ? `Colocar no U${u}` : `Não cabe: o equipamento ocupa ${altura}U a partir daqui` });
    }
    return lista;
  });

  /** Linha da grade (1 = topo) para algo que começa no U `u` e ocupa `alturaU` U. */
  protected linha(u: number, alturaU: number): string {
    const altura = Math.max(1, alturaU);
    const topo = u + altura - 1;
    return `${this.altura() - topo + 1} / span ${altura}`;
  }

  protected tipo(e: EquipamentoResumo): string {
    return ROTULOS_TIPO_EQUIPAMENTO[e.tipo];
  }
}
