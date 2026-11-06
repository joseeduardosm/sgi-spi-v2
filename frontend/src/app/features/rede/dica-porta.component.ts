// Criado por José Eduardo Santana Martins
// Este arquivo serve para a dica da porta de rede (passar o mouse): a configuração toda, formatada, sem precisar abrir a porta.

import { DatePipe } from '@angular/common';
import { Component, input } from '@angular/core';

import { COR_STATUS_PORTA, modoPorta, Porta, ROTULOS_STATUS_PORTA, textoVlanPorta, velocidade } from './rede.models';

/** Onde a dica aparece (coordenadas da janela): ao lado do quadradinho da porta, virando para a esquerda se faltar espaço. */
export function posicaoDaDica(alvo: HTMLElement): { x: number; y: number } {
  const caixa = alvo.getBoundingClientRect();
  const largura = 300;
  const x = caixa.right + 8 + largura <= window.innerWidth ? caixa.right + 8 : Math.max(8, caixa.left - largura - 8);
  return { x, y: Math.max(8, Math.min(caixa.top, window.innerHeight - 280)) };
}

/** Usada na face do equipamento e no caminho até o core (mesmo desenho da dica do quadro de Tarefas). */
@Component({
  selector: 'app-dica-porta',
  imports: [DatePipe],
  template: `
    <div class="dica-porta" role="tooltip" [id]="idDica()" [style.left.px]="x()" [style.top.px]="y()">
      <header>
        <strong>Porta <span class="texto-codigo">{{ porta().nome || porta().numero_logico }}</span></strong>
        <span class="selo-status" [attr.data-chamado]="corStatus()">{{ textoStatus() }}</span>
      </header>
      @if (porta().descricao) { <p class="descricao-dica-porta">{{ porta().descricao }}</p> }
      <dl>
        <!-- Patch panel não tem parte lógica: sem modo, VLAN, IP e velocidade -->
        @if (!passiva()) {
          <dt>Modo</dt><dd>{{ modo(porta()) }}</dd>
          @if (porta().modo === 'roteada') {
            <dt>IP</dt><dd class="texto-codigo">{{ porta().ip_interface || '—' }}</dd>
          } @else {
            <dt>VLANs</dt><dd>{{ vlans(porta()) }}</dd>
          }
        }
        <dt>Ligada a</dt><dd>{{ porta().conexao?.texto || 'Nada cadastrado' }}</dd>
        @if (porta().ponto) { <dt>Ponto</dt><dd class="texto-codigo">{{ porta().ponto }}</dd> }
        @if (porta().velocidade_mbps && !passiva()) { <dt>Velocidade</dt><dd>{{ vel(porta().velocidade_mbps) }}@if (porta().duplex) { · {{ porta().duplex === 'full' ? 'full duplex' : 'half duplex' }} }</dd> }
        @if (porta().mac) { <dt>MAC</dt><dd class="texto-codigo">{{ porta().mac }}</dd> }
        @if (porta().erros_entrada || porta().erros_saida) { <dt>Erros</dt><dd>{{ porta().erros_entrada }} entrada · {{ porta().erros_saida }} saída</dd> }
        @if (porta().ultima_mudanca) { <dt>Mudou em</dt><dd>{{ porta().ultima_mudanca | date: 'dd/MM/yyyy HH:mm' }}</dd> }
        @if (porta().chamados_abertos) { <dt>Chamados</dt><dd>{{ porta().chamados_abertos }} aberto(s)</dd> }
      </dl>
    </div>
  `,
  styles: [`
/* Dica da porta (passar o mouse): mesmo desenho da dica do quadro de Tarefas, com os tokens do tema */
.dica-porta {
  position: fixed;
  z-index: 1100;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 300px;
  padding: 12px 14px;
  border: 1px solid var(--spi-borda);
  border-radius: var(--spi-raio-m);
  color: var(--spi-texto);
  background: var(--spi-superficie);
  box-shadow: var(--spi-sombra-flutuante);
  font-size: var(--spi-texto-legenda);
  line-height: 1.4;
  pointer-events: none;

  header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  strong { font-size: var(--spi-texto-compacto); }
  .descricao-dica-porta { margin: 0; overflow-wrap: anywhere; }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; margin: 0; padding-top: 8px; border-top: 1px solid var(--spi-borda); }
  dt { color: var(--spi-apagado); }
  dd { margin: 0; overflow-wrap: anywhere; }
}


  `],
})
export class DicaPortaComponent {
  readonly porta = input.required<Porta>();
  readonly x = input(0);
  readonly y = input(0);
  readonly idDica = input('');
  /** Porta de patch panel: a dica não mostra a parte lógica. */
  readonly passiva = input(false);

  protected corStatus(): string {
    const s = this.porta().status;
    return s ? COR_STATUS_PORTA[s] : 'neutro';
  }

  protected textoStatus(): string {
    const s = this.porta().status;
    return s ? ROTULOS_STATUS_PORTA[s] : 'Sem informação';
  }

  protected modo(p: Porta): string {
    return modoPorta(p.modo).rotulo;
  }

  /** Access: só a VLAN; os outros modos: o resumo de nativa, sem tag, com tag e voz. */
  protected vlans(p: Porta): string {
    if (p.modo === 'access') return p.vlan_nativa ? `VLAN ${p.vlan_nativa}${p.vlan_voz ? ' · voz ' + p.vlan_voz : ''}` : 'Nenhuma';
    return p.vlan_nativa || p.vlans_tag.length || p.vlans_sem_tag.length || p.vlan_voz ? textoVlanPorta(p) : 'Nenhuma';
  }

  protected vel(mbps: number | null): string {
    return velocidade(mbps);
  }
}
