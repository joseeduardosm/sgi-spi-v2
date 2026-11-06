// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar a face de um equipamento (as portas na posição real); clicar na porta abre o detalhe dela.

import { Component, computed, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { DicaPortaComponent, posicaoDaDica } from './dica-porta.component';
import { EquipamentoDetalhe, Porta, ROTULOS_STATUS_PORTA, textoVlanPorta } from './rede.models';

/** Estado desenhado: verde = ligada, vermelho = desligada, cinza = desativada ou sem informação (decisão do usuário). */
type EstadoFace = 'up' | 'down' | 'sem';

interface CelulaPorta { porta: Porta; linha: number; coluna: number }

@Component({
  selector: 'app-face-rede',
  imports: [RouterLink, DicaPortaComponent],
  host: { '(window:scroll)': 'dica.set(null)' },
  styleUrl: './face-rede.component.scss',
  template: `
    @if (e().modelo; as m) {
      <figure class="face" [attr.aria-label]="'Face de ' + e().nome">
        <div class="face-rolagem">
          <div class="face-equipamento">
            <div class="face-grade" [style.grid-template-columns]="'repeat(' + m.colunas + ', var(--tamanho-porta))'"
              [style.grid-template-rows]="'repeat(' + m.linhas + ', var(--tamanho-porta))'">
              @for (c of grade(); track c.porta.id) {
                <a class="porta-face" [routerLink]="['/rede/portas', c.porta.id]" [style.grid-row]="c.linha" [style.grid-column]="c.coluna"
                  [attr.data-estado]="estado(c.porta)" [attr.aria-label]="rotulo(c.porta)" [attr.aria-describedby]="dica()?.porta === c.porta ? idDica : null"
                  (mouseenter)="mostrarDica($event, c.porta)" (mouseleave)="dica.set(null)" (focus)="mostrarDica($event, c.porta)" (blur)="dica.set(null)">
                  {{ c.porta.numero_logico }}
                  @if (c.porta.chamados_abertos) { <span class="marca-chamado" aria-hidden="true"></span> }
                </a>
              }
            </div>
            @if (extras().length) {
              <div class="face-extras" role="group" aria-label="Portas extras (uplink e fibra)">
                @for (p of extras(); track p.id) {
                  <a class="porta-face extra" [routerLink]="['/rede/portas', p.id]" [attr.data-estado]="estado(p)" [attr.aria-label]="rotulo(p)" [attr.aria-describedby]="dica()?.porta === p ? idDica : null"
                  (mouseenter)="mostrarDica($event, p)" (mouseleave)="dica.set(null)" (focus)="mostrarDica($event, p)" (blur)="dica.set(null)">
                    {{ p.nome || p.numero_logico }}
                    @if (p.chamados_abertos) { <span class="marca-chamado" aria-hidden="true"></span> }
                  </a>
                }
              </div>
            }
          </div>
        </div>
        <figcaption class="face-legenda">
          <span><span class="amostra" data-estado="up"></span>Ligada</span>
          <span><span class="amostra" data-estado="down"></span>Desligada</span>
          <span><span class="amostra" data-estado="sem"></span>Desativada ou sem informação</span>
          <span><span class="marca-chamado legenda"></span>Com chamado aberto</span>
          <span class="face-dica">Passe o mouse para ver a configuração; clique para alterar.</span>
        </figcaption>
      </figure>
    }

    <!-- Dica da porta: a configuração toda, formatada, sem precisar abrir a porta -->
    @if (dica(); as d) { <app-dica-porta [porta]="d.porta" [x]="d.x" [y]="d.y" [idDica]="idDica" [passiva]="e().tipo === 'patch_panel'" /> }
  `,
})
export class FaceRedeComponent {
  readonly e = input.required<EquipamentoDetalhe>();

  private static sequencia = 0;
  protected readonly idDica = `dica-porta-${++FaceRedeComponent.sequencia}`;
  /** Porta sob o mouse (ou com o foco do teclado) e onde a dica aparece, em coordenadas da janela. */
  protected readonly dica = signal<{ porta: Porta; x: number; y: number } | null>(null);

  /** Portas da grade, na linha e coluna dadas pelo modelo (numeração por coluna ou por linha). */
  protected readonly grade = computed<CelulaPorta[]>(() => {
    const posicoes = this.e().posicoes;
    return this.e().portas.filter((p) => posicoes[p.numero_logico]).map((p) => ({ porta: p, linha: posicoes[p.numero_logico][0], coluna: posicoes[p.numero_logico][1] }));
  });
  /** As que ficam fora da grade (uplink, fibra e qualquer número acima dela). */
  protected readonly extras = computed(() => this.e().portas.filter((p) => !this.e().posicoes[p.numero_logico]));

  protected estado(p: Porta): EstadoFace {
    return p.status === 'up' ? 'up' : p.status === 'down' ? 'down' : 'sem';
  }

  /** Texto para leitor de tela e dica do mouse: a cor nunca é o único sinal. */
  protected rotulo(p: Porta): string {
    const partes = [`Porta ${p.nome || p.numero_logico}`, p.status ? ROTULOS_STATUS_PORTA[p.status] : 'sem informação'];
    if (p.descricao) partes.push(p.descricao);
    if (p.vlan_nativa || p.vlans_tag.length || p.modo === 'roteada') partes.push(p.modo === 'access' ? `VLAN ${p.vlan_nativa}` : textoVlanPorta(p));
    if (p.conexao) partes.push(`ligada a ${p.conexao.texto}`);
    if (p.chamados_abertos) partes.push(`${p.chamados_abertos} chamado(s) aberto(s)`);
    return partes.join(', ');
  }

  /** Mesmo jeito da dica do quadro de Tarefas: ao lado da porta, virando para a esquerda se faltar espaço, sempre dentro da janela. */
  protected mostrarDica(evento: Event, p: Porta): void {
    this.dica.set({ porta: p, ...posicaoDaDica(evento.currentTarget as HTMLElement) });
  }
}
