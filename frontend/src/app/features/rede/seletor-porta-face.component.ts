/**
 * =============================================================================
 * ARQUIVO: seletor-porta-face.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Escolher uma porta clicando no desenho da face do equipamento (as portas no
 * lugar em que ficam no switch ou no patch panel), no lugar de uma lista longa.
 *
 * RESUMO TÉCNICO:
 * Componente standalone. Recebe o modelo de face (para a grade), as posições
 * (número da porta → linha e coluna) e as opções {id, numero, nome, livre,
 * dica}. Cada porta é um rótulo com um botão de opção (radio) escondido, para
 * o teclado (setas) e o leitor de tela funcionarem como num grupo de opções.
 * Livre = clicável; ocupada = apagada e desativada; a escolhida fica em
 * vermelho (o acento do sistema para o item ativo). Reaproveita o visual de
 * face-rede.component.scss. Emite `valorChange` com o id escolhido.
 *
 * FINALIDADE DE NEGÓCIO:
 * Pedido do usuário (17/11/2026): no passo Conexão do cadastro do
 * equipamento, escolher a porta deste equipamento e a do outro pela face,
 * vendo o que está livre, em vez de rolar uma lista de 48 números.
 *
 * CONTEXTO NO SISTEMA:
 * Usado em cadastro-equipamento-rede.component.ts ("Porta deste equipamento"
 * e "Porta do outro equipamento").
 *
 * =============================================================================
 */

import { Component, computed, input, output } from '@angular/core';

import { ModeloFace } from './rede.models';

/** Uma porta que aparece na face para escolher. `livre` = pode ser escolhida; `dica` = o texto do mouse (o que está ligado nela, por exemplo). */
export interface OpcaoPortaFace { id: string; numero: number; nome: string; livre: boolean; dica: string }

/** Posição da porta na grade da face (linha e coluna, começando em 1), igual à de `posicoes()` no backend. */
export function posicoesDoModelo(m: ModeloFace | null | undefined): Record<string, [number, number]> {
  const resultado: Record<string, [number, number]> = {};
  if (!m) return resultado;
  for (let i = 0; i < m.linhas * m.colunas; i++) {
    // Numeração por coluna: 1 em cima, 2 embaixo, 3 em cima...; por linha: 1..N na primeira linha
    resultado[i + 1] = m.numeracao === 'coluna' ? [(i % m.linhas) + 1, Math.floor(i / m.linhas) + 1] : [Math.floor(i / m.colunas) + 1, (i % m.colunas) + 1];
  }
  return resultado;
}

/** Recursos do Angular: `input()` = entrada do pai (lida como função), `output()` = evento para o pai, `computed()` = valor recalculado sozinho. */
@Component({
  selector: 'app-seletor-porta-face',
  styleUrls: ['./face-rede.component.scss'],
  styles: [`
    /* Porta para escolher: rótulo com o radio escondido; livre = contorno, ocupada = apagada, escolhida = vermelho */
    .face .porta-face { cursor: pointer; color: var(--spi-texto); background: var(--spi-superficie); }
    .face .porta-face[data-estado='ocupada'] { cursor: not-allowed; color: var(--spi-apagado); background: var(--spi-superficie-alt); border-style: dashed; opacity: .6; }
    .face .porta-face[data-estado='ocupada']:hover { box-shadow: none; }
    .face .porta-face[data-estado='escolhida'] { color: var(--spi-superficie); background: var(--spi-vermelho); border-color: var(--spi-vermelho); }
    .face .porta-face:has(input:focus-visible) { box-shadow: var(--spi-anel-foco); }
    .face .porta-face input { position: absolute; width: 1px; height: 1px; margin: 0; opacity: 0; pointer-events: none; }
    .face .amostra[data-estado='livre'] { background: var(--spi-superficie); }
    .face .amostra[data-estado='ocupada'] { background: var(--spi-superficie-alt); border-style: dashed; }
    .face .amostra[data-estado='escolhida'] { background: var(--spi-vermelho); border-color: var(--spi-vermelho); }
  `],
  template: `
    @if (modelo()) {
      <figure class="face" role="radiogroup" [attr.aria-label]="rotulo()">
        <div class="face-rolagem">
          <div class="face-equipamento">
            <div class="face-grade" [style.grid-template-columns]="'repeat(' + modelo()!.colunas + ', var(--tamanho-porta))'"
              [style.grid-template-rows]="'repeat(' + modelo()!.linhas + ', var(--tamanho-porta))'">
              @for (o of grade(); track o.id) {
                <label class="porta-face" [style.grid-row]="posicoes()[o.numero][0]" [style.grid-column]="posicoes()[o.numero][1]" [attr.data-estado]="estado(o)" [title]="o.dica">
                  <input type="radio" [name]="nome()" [value]="o.id" [checked]="o.id === valor()" [disabled]="!o.livre" [attr.aria-label]="'Porta ' + o.nome + ', ' + o.dica"
                    (change)="valorChange.emit(o.id)" />
                  {{ o.numero }}
                </label>
              }
            </div>
            @if (extras().length) {
              <div class="face-extras" role="group" aria-label="Portas extras (uplink e fibra)">
                @for (o of extras(); track o.id) {
                  <label class="porta-face extra" [attr.data-estado]="estado(o)" [title]="o.dica">
                    <input type="radio" [name]="nome()" [value]="o.id" [checked]="o.id === valor()" [disabled]="!o.livre" [attr.aria-label]="'Porta ' + o.nome + ', ' + o.dica"
                      (change)="valorChange.emit(o.id)" />
                    {{ o.nome }}
                  </label>
                }
              </div>
            }
          </div>
        </div>
        <figcaption class="face-legenda">
          <span><span class="amostra" data-estado="livre"></span>Livre (clique para escolher)</span>
          <span><span class="amostra" data-estado="ocupada"></span>Ocupada ou não serve</span>
          <span><span class="amostra" data-estado="escolhida"></span>Escolhida</span>
        </figcaption>
      </figure>
    } @else {
      <p class="dica-formulario">Sem modelo de face: não dá para desenhar as portas.</p>
    }
  `,
})
export class SeletorPortaFaceComponent {
  readonly modelo = input.required<ModeloFace | null>();
  /** Número da porta → [linha, coluna] (o `posicoes` do equipamento, ou `posicoesDoModelo` para um equipamento ainda não cadastrado). */
  readonly posicoes = input.required<Record<string, [number, number]>>();
  readonly opcoes = input.required<OpcaoPortaFace[]>();
  /** Id da porta escolhida. */
  readonly valor = input<string | null>(null);
  /** Nome do grupo de radios (único na tela) e o rótulo para o leitor de tela. */
  readonly nome = input.required<string>();
  readonly rotulo = input('Escolha a porta');
  readonly valorChange = output<string>();

  /** Portas da grade (as que têm posição) e as extras (uplink, fibra), como na face do equipamento. */
  protected readonly grade = computed(() => this.opcoes().filter((o) => this.posicoes()[o.numero]));
  protected readonly extras = computed(() => this.opcoes().filter((o) => !this.posicoes()[o.numero]));

  protected estado(o: OpcaoPortaFace): 'escolhida' | 'livre' | 'ocupada' {
    return o.id === this.valor() ? 'escolhida' : o.livre ? 'livre' : 'ocupada';
  }
}
