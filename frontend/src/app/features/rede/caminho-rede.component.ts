// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar o caminho de uma porta até o core: caixas em cascata (como as da Topologia) ligadas pelos cabos.

import { NgTemplateOutlet } from '@angular/common';
import { Component, effect, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DicaPortaComponent, posicaoDaDica } from './dica-porta.component';
import { RedeApiService } from './rede-api.service';
import { CaminhoRede, EtapaCaminho, Porta, ROTULOS_FUNCAO_EQUIPAMENTO, ROTULOS_PING, ROTULOS_TIPO_EQUIPAMENTO } from './rede.models';

/**
 * Cascata de caixas, de cima (core) para baixo: cada caixa é um equipamento (ou o ponto de rede no fim), com o tipo, a função e o ping.
 * Cada caixa tem o quadradinho da porta que sobe (canto superior direito) e o da porta que desce (canto inferior direito), iguais aos da face;
 * o cabo é só o traço entre o quadradinho de baixo de uma caixa e o de cima da seguinte (as portas estão nos quadradinhos e na dica). Os dispositivos ligados na porta (telefone → computador)
 * ficam lado a lado na última linha. Mesmo desenho das caixas da Topologia (borda de 1px, raio médio, rótulo em caixa alta).
 * `versao`: qualquer valor que mude quando a ligação da porta muda (a cascata se recarrega).
 */
@Component({
  selector: 'app-caminho-rede',
  imports: [NgTemplateOutlet, RouterLink, DicaPortaComponent, EsqueletoComponent],
  template: `
    @if (caminho(); as c) {
      <ol class="cascata-caminho" aria-label="Caminho do core até a porta">
        @for (e of c.etapas; track $index) {
          <li>
            <!-- O cabo é só o traço entre os quadradinhos (as portas estão neles e na dica); o texto fica para o leitor de tela -->
            @if (e.cabo) { <span class="cabo-caminho"><span class="somente-leitor-tela">Cabo {{ e.cabo }}</span></span> }
            <div class="caixa-caminho">
              @if (e.porta_entrada; as p) { <ng-container [ngTemplateOutlet]="quadradinho" [ngTemplateOutletContext]="{ $implicit: p, lado: 'porta-cima' }" /> }
              <span class="tipo-caminho">{{ rotulo(e) }}</span>
              @if (e.equipamento_id) { <a [routerLink]="['/rede/equipamentos', e.equipamento_id]"><strong>{{ e.nome }}</strong></a> }
              @else { <strong class="texto-codigo">{{ e.nome }}</strong> }
              @if (e.ping_situacao) {
                <span class="selo-status" [attr.data-chamado]="e.ping_situacao === 'no_ar' ? 'sucesso' : 'perigo'">{{ ping(e) }}</span>
              }
              @if (e.porta_saida; as p) { <ng-container [ngTemplateOutlet]="quadradinho" [ngTemplateOutletContext]="{ $implicit: p, lado: 'porta-baixo' }" /> }
            </div>
          </li>
        }
        @if (c.dispositivos.length) {
          <li>
            <span class="cabo-caminho"><span class="somente-leitor-tela">Cabo na porta {{ c.cabo_dispositivos }}</span></span>
            <div class="dispositivos-caminho">
              @for (d of c.dispositivos; track $index) {
                <div class="caixa-caminho">
                  <span class="tipo-caminho">{{ $index === 0 ? 'Ligado na porta' : 'Atrás do anterior' }}</span>
                  @if (d.bem_id) { <a [routerLink]="['/patrimonio/bens', d.bem_id]"><strong>{{ d.texto }}</strong></a> } @else { <strong>{{ d.texto }}</strong> }
                </div>
              }
            </div>
          </li>
        }
      </ol>
      @if (c.aviso) { <p class="dica-formulario aviso-caminho">{{ c.aviso }}</p> }
    } @else if (erro()) {
      <p class="estado-vazio">Não foi possível montar o caminho.</p>
    } @else {
      <app-esqueleto tipo="lista" [linhas]="3" />
    }

    <!-- Quadradinho da porta, igual ao da face do equipamento (cor pelo status); passar o mouse mostra a mesma dica, clicar abre a porta -->
    <ng-template #quadradinho let-p let-lado="lado">
      <a class="porta-face" [class]="lado" [class.porta-atual]="p.id === portaId()" [attr.aria-current]="p.id === portaId() ? 'true' : null" [routerLink]="['/rede/portas', p.id]" [attr.data-estado]="estado(p)" [attr.aria-label]="'Porta ' + (p.nome || p.numero_logico)"
         [attr.aria-describedby]="dica()?.porta === p ? idDica : null"
         (mouseenter)="mostrarDica($event, p)" (mouseleave)="dica.set(null)" (focus)="mostrarDica($event, p)" (blur)="dica.set(null)">{{ p.numero_logico }}</a>
    </ng-template>
    @if (dica(); as d) { <app-dica-porta [porta]="d.porta" [x]="d.x" [y]="d.y" [idDica]="idDica" /> }
  `,
  styleUrls: ['./face-rede.component.scss', './caminho-rede.component.scss'],
  host: { '(window:scroll)': 'dica.set(null)' },
})
export class CaminhoRedeComponent {
  readonly portaId = input.required<string>();
  readonly versao = input<unknown>(null);
  private readonly api = inject(RedeApiService);

  private static sequencia = 0;
  protected readonly idDica = `dica-caminho-${++CaminhoRedeComponent.sequencia}`;
  protected readonly caminho = signal<CaminhoRede | null>(null);
  /** Porta sob o mouse e onde a dica aparece. */
  protected readonly dica = signal<{ porta: Porta; x: number; y: number } | null>(null);
  protected readonly erro = signal(false);

  constructor() {
    effect(() => {
      const id = this.portaId();
      this.versao();
      this.erro.set(false);
      this.api.caminho(id).subscribe({ next: (c) => this.caminho.set(c), error: () => this.erro.set(true) });
    });
  }

  protected rotulo(e: EtapaCaminho): string {
    if (e.tipo === 'ponto') return 'Ponto de rede';
    const tipo = e.tipo_equipamento ? ROTULOS_TIPO_EQUIPAMENTO[e.tipo_equipamento] : 'Equipamento';
    return e.funcao ? `${tipo} · ${ROTULOS_FUNCAO_EQUIPAMENTO[e.funcao]}` : tipo;
  }

  protected estado(p: Porta): 'up' | 'down' | 'sem' {
    return p.status === 'up' ? 'up' : p.status === 'down' ? 'down' : 'sem';
  }

  protected mostrarDica(evento: Event, p: Porta): void {
    this.dica.set({ porta: p, ...posicaoDaDica(evento.currentTarget as HTMLElement) });
  }

  protected ping(e: EtapaCaminho): string {
    return e.ping_situacao ? ROTULOS_PING[e.ping_situacao] : '';
  }
}
