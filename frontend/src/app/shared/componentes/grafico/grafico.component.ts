// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar gráficos (barras, linhas e rosca) com o Chart.js, no padrão visual do portal.

import {
  ChangeDetectionStrategy, Component, computed, DestroyRef, effect, ElementRef, inject, input, untracked, viewChild,
} from '@angular/core';
import {
  ArcElement, BarController, BarElement, CategoryScale, Chart, ChartConfiguration, DoughnutController, Filler, Legend, LinearScale, LineController,
  LineElement, PointElement, Tooltip,
} from 'chart.js';

import { abreviar, descreverSerie, FormatoGrafico, formatarValor } from './grafico.formatos';

// Registra só o que o portal usa (o Chart.js fica menor no pacote final)
Chart.register(ArcElement, BarController, BarElement, CategoryScale, DoughnutController, Filler, Legend, LinearScale, LineController, LineElement, PointElement, Tooltip);

/** Cores da identidade do portal para as séries, na ordem de uso. */
export const CORES_GRAFICO = ['#c82331', '#2f5d8a', '#2f9e6b', '#e0a100', '#7b8490', '#8a4fb3'];

export interface SerieGrafico {
  nome: string;
  dados: number[];
  /** Cor da série; sem ela, usa a paleta na ordem. */
  cor?: string;
  /** Só para gráficos de barras: desenha esta série como linha por cima. */
  linha?: boolean;
}

/**
 * Gráfico acessível: o canvas tem `aria-label` e há uma descrição em texto para leitores de tela.
 * Redimensiona com o contêiner e é destruído ao sair da tela.
 */
@Component({
  selector: 'app-grafico',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="caixa-grafico" [class.preencher]="altura() === 0" [style.height.px]="altura() || null">
      <canvas #tela role="img" [attr.aria-label]="titulo()"></canvas>
    </div>
    <ul class="somente-leitor-tela">
      @for (d of descricoes(); track $index) { <li>{{ d }}</li> }
    </ul>
  `,
})
export class GraficoComponent {
  readonly tipo = input<'bar' | 'line' | 'doughnut'>('bar');
  readonly rotulos = input.required<string[]>();
  readonly series = input.required<SerieGrafico[]>();
  readonly titulo = input('Gráfico');
  readonly formato = input<FormatoGrafico>('numero');
  /** Altura em px; 0 faz o gráfico preencher todo o espaço disponível do contêiner (painéis em tela cheia). */
  readonly altura = input(240);
  readonly empilhado = input(false);
  /** Barras na horizontal (bom para nomes longos, como setores). */
  readonly horizontal = input(false);
  /** Esconde a legenda (útil quando há uma única série). */
  readonly semLegenda = input(false);

  private readonly tela = viewChild.required<ElementRef<HTMLCanvasElement>>('tela');
  private grafico: Chart | null = null;
  protected readonly descricoes = computed(() => this.series().map((s) => descreverSerie(s.nome, this.rotulos(), s.dados, this.formato())));

  constructor() {
    effect(() => {
      const configuracao = this.configuracao();
      // `untracked`: criar/atualizar o gráfico não deve religar o efeito
      untracked(() => this.desenhar(configuracao));
    });
    inject(DestroyRef).onDestroy(() => this.grafico?.destroy());
  }

  private desenhar(configuracao: ChartConfiguration): void {
    if (this.grafico) {
      this.grafico.data = configuracao.data;
      this.grafico.options = configuracao.options ?? {};
      this.grafico.update();
      return;
    }
    const contexto = this.tela().nativeElement.getContext('2d');
    if (contexto) this.grafico = new Chart(contexto, configuracao);
  }

  /** Tamanho inicial da fonte, de 11 a 24 px, conforme a largura do contêiner. */
  private tamanhoFonte(): number {
    const largura = this.tela().nativeElement.parentElement?.clientWidth ?? 600;
    return Math.round(Math.min(24, Math.max(11, largura / 60)));
  }

  private configuracao(): ChartConfiguration {
    const tipo = this.tipo();
    const formato = this.formato();
    const series = this.series();
    const reduzir = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    const cor = (s: SerieGrafico, i: number) => s.cor ?? CORES_GRAFICO[i % CORES_GRAFICO.length];
    const datasets = tipo === 'doughnut'
      ? [{ label: series[0]?.nome ?? '', data: series[0]?.dados ?? [], backgroundColor: this.rotulos().map((_, i) => CORES_GRAFICO[i % CORES_GRAFICO.length]), borderWidth: 2 }]
      : series.map((s, i) => ({
          type: (s.linha ? 'line' : tipo) as 'bar' | 'line', label: s.nome, data: s.dados, borderColor: cor(s, i), cubicInterpolationMode: 'monotone' as const,
          backgroundColor: tipo === 'line' || s.linha ? cor(s, i) + '33' : cor(s, i), fill: tipo === 'line' && series.length === 1,
          borderWidth: tipo === 'line' || s.linha ? 2.5 : 0, pointRadius: tipo === 'line' || s.linha ? 3 : 0, borderRadius: tipo === 'bar' && !s.linha ? 4 : 0,
          maxBarThickness: 36,
        }));
    return {
      type: tipo as 'bar',
      data: { labels: this.rotulos(), datasets: datasets as never },
      options: {
        responsive: true, maintainAspectRatio: false, animation: reduzir ? false : { duration: 500 },
        indexAxis: this.horizontal() ? 'y' : 'x',
        plugins: {
          legend: { display: !this.semLegenda() && (series.length > 1 || tipo === 'doughnut'), position: tipo === 'doughnut' ? 'right' : 'bottom', labels: { boxWidth: 12 } },
          tooltip: { callbacks: { label: (c) => `${c.dataset.label ?? c.label}: ${formatarValor(Number(c.parsed.y ?? c.parsed.x ?? c.parsed), formato)}` } },
        },
        // Eixo das categorias (rótulos) e eixo dos valores; na barra horizontal eles trocam de lado
        scales: tipo === 'doughnut' ? {} : this.horizontal()
          ? {
              x: { type: 'linear', stacked: this.empilhado(), beginAtZero: true, ticks: { precision: 0, callback: (v) => abreviar(Number(v)) } },
              y: { type: 'category', stacked: this.empilhado(), grid: { display: false } },
            }
          : {
              x: { type: 'category', stacked: this.empilhado(), grid: { display: false } },
              y: { type: 'linear', stacked: this.empilhado(), beginAtZero: true, ticks: { precision: 0, callback: (v) => abreviar(Number(v)) } },
            },
        // Fonte proporcional à largura do gráfico (legível também numa TV)
        font: { size: this.tamanhoFonte() },
        onResize: (grafico, tamanho) => { grafico.options.font = { size: Math.round(Math.min(24, Math.max(11, tamanho.width / 60))) }; },
      },
    };
  }
}
