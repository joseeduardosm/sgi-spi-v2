// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar o passo a passo de um fluxo como uma trilha numerada (1 → 2 → 3…), igual à da competência da execução.

import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, model, output } from '@angular/core';

/** Situação de um passo: concluído (✓ verde), em andamento (vermelho), aguardando (cinza), bloqueado (apagado e sem clique) ou recusado (vermelho suave). */
export type EstadoEtapa = 'concluida' | 'atual' | 'aguardando' | 'bloqueada' | 'recusada';

export interface EtapaTrilha {
  /** Identificador do passo (devolvido em `selecionada`). */
  id: string;
  rotulo: string;
  estado: EstadoEtapa;
  /** Texto pequeno sob o rótulo; sem ele, o padrão do estado ("concluída", "em andamento", "aguardando"). */
  subtitulo?: string;
  /** Dica ao passar o mouse (ex.: quem fez e quando). */
  titulo?: string;
  /** Passo opcional (aparece como "opcional" no subtítulo quando ainda não foi feito). */
  opcional?: boolean;
}

const SUBTITULO_PADRAO: Record<EstadoEtapa, string> = {
  concluida: 'concluída', atual: 'em andamento', aguardando: 'aguardando', bloqueada: 'aguardando', recusada: 'recusada',
};

/**
 * Trilha de etapas do sistema: bolinhas numeradas ligadas por uma linha (verde onde já passou, vermelha entre passos em andamento),
 * com a barra "X de N etapas concluídas". É o padrão de todo fluxo com 3 ou mais passos sequenciais (ver DESIGN.md).
 * `compacta` serve para cartões e listas (sem barra de progresso, bolinhas menores). Passos paralelos = mais de um `atual`.
 * Com `navegavel`, cada passo vira botão e escolhe a etapa mostrada (`selecionada`); passos bloqueados não recebem clique.
 */
@Component({
  selector: 'app-trilha-etapas',
  imports: [NgTemplateOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './trilha-etapas.component.html',
  styleUrl: './trilha-etapas.component.scss',
})
export class TrilhaEtapasComponent {
  readonly etapas = input.required<EtapaTrilha[]>();
  readonly ariaLabel = input('Etapas do fluxo');
  readonly mostrarProgresso = input(true);
  readonly compacta = input(false);
  readonly navegavel = input(false);
  /** Passo mostrado na tela quando a trilha é navegável. */
  readonly selecionada = model<string | null>(null);
  readonly escolheu = output<string>();

  protected readonly concluidas = computed(() => this.etapas().filter((e) => e.estado === 'concluida').length);
  protected readonly percentual = computed(() => {
    const total = this.etapas().length || 1;
    return ((100 * this.concluidas()) / total).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  });
  protected readonly larguraBarra = computed(() => (100 * this.concluidas()) / (this.etapas().length || 1));

  /** Cor da linha entre um passo e o seguinte: verde (feito), vermelha (os dois em andamento) ou cinza. */
  protected ligacao(i: number): 'verde' | 'vermelha' | 'cinza' {
    const lista = this.etapas();
    const a = lista[i], b = lista[i + 1];
    if (!a || !b) return 'cinza';
    if (a.estado === 'concluida' && (b.estado === 'concluida' || b.estado === 'atual')) return 'verde';
    if (a.estado === 'atual' && b.estado === 'atual') return 'vermelha';
    return 'cinza';
  }

  protected subtitulo(e: EtapaTrilha): string {
    if (e.subtitulo) return e.subtitulo;
    if (e.opcional && e.estado !== 'concluida' && e.estado !== 'atual') return 'opcional';
    return SUBTITULO_PADRAO[e.estado];
  }

  protected escolher(e: EtapaTrilha): void {
    if (e.estado === 'bloqueada') return;
    this.selecionada.set(e.id);
    this.escolheu.emit(e.id);
  }
}
