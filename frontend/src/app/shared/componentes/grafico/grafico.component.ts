// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar gráficos (barras, linhas e rosca) com o Chart.js, no padrão visual do portal.

import {
  ChangeDetectionStrategy, Component, computed, DestroyRef, effect, ElementRef, inject, input, output, signal, untracked, viewChild,
} from '@angular/core';
import {
  ArcElement, BarController, BarElement, CategoryScale, Chart, ChartConfiguration, DoughnutController, Filler, Legend, LinearScale, LineController,
  LineElement, PointElement, Plugin, Tooltip,
} from 'chart.js';

import { abreviar, descreverSerie, FormatoGrafico, formatarValor } from './grafico.formatos';

// Registra só o que o portal usa (o Chart.js fica menor no pacote final)
Chart.register(ArcElement, BarController, BarElement, CategoryScale, DoughnutController, Filler, Legend, LinearScale, LineController, LineElement, PointElement, Tooltip);

Chart.defaults.font.family = "'Inter', Arial, Helvetica, sans-serif";

/** Cores da identidade do portal para as séries, na ordem de uso. */
export const CORES_GRAFICO = ['#c82331', '#2f5d8a', '#2f9e6b', '#e0a100', '#7b8490', '#8a4fb3'];

export interface SerieGrafico {
  nome: string;
  /** `null` deixa um buraco na linha (ex.: dias futuros do burndown). */
  dados: (number | null)[];
  /** Cor da série; sem ela, usa a paleta na ordem. */
  cor?: string;
  /** Barras: séries com a mesma `pilha` ficam empilhadas na mesma coluna (ex.: pago + excedente); as demais ficam lado a lado. */
  pilha?: string;
  /** Só para gráficos de barras: desenha esta série como linha por cima. */
  linha?: boolean;
  /** Linha pontilhada (ex.: a linha ideal do burndown). */
  tracejada?: boolean;
  /** Preenche a área sob a linha (com `empilhado`, vira área empilhada). */
  area?: boolean;
  /** Linha sem bolinhas nos pontos (séries diárias longas). */
  semPontos?: boolean;
}

/** Cores lidas do tema ativo (claro ou escuro) no momento de desenhar. */
function coresDoTema(): { texto: string; apagado: string; linha: string; fundo: string; escuro: boolean } {
  const css = getComputedStyle(document.documentElement);
  const ler = (nome: string, padrao: string) => css.getPropertyValue(nome).trim() || padrao;
  const escuro = document.documentElement.getAttribute('data-tema') === 'escuro';
  return {
    texto: ler('--spi-titulo', escuro ? '#f2f4f6' : '#17202a'),
    apagado: ler('--spi-apagado', escuro ? '#a3adb8' : '#586372'),
    linha: escuro ? '#ffffff2e' : '#0000002e',
    fundo: ler('--cor-ffffff', escuro ? '#1b2229' : '#ffffff'),
    escuro,
  };
}

/** Linha vertical que acompanha o ponteiro nos gráficos de linha (como o cursor do gráfico do Spell). */
const cursorVertical: Plugin = {
  id: 'cursorVertical',
  afterDatasetsDraw(grafico) {
    const ativos = grafico.getActiveElements();
    if (!ativos.length || (grafico.config as unknown as { type: string }).type !== 'line') return;
    const { ctx, chartArea } = grafico;
    const x = ativos[0].element.x;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = coresDoTema().linha;
    ctx.stroke();
    ctx.restore();
  },
};

/**
 * Gráfico acessível: o canvas tem `aria-label` e há uma descrição em texto para leitores de tela.
 * Redimensiona com o contêiner e é destruído ao sair da tela.
 */
/** Valor numérico de um ponto: no gráfico horizontal ele está em `x` (o `y` é o índice da categoria); na rosca é o próprio número. */
function valorDoPonto(parsed: unknown, horizontal: boolean): number {
  if (typeof parsed === 'number') return parsed;
  const p = parsed as { x: number; y: number };
  return horizontal ? p.x : p.y;
}

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
  /** Com `clicavel`, o ponteiro vira "mãozinha" sobre as barras/fatias e o clique emite o índice. */
  readonly clicavel = input(false);
  readonly itemClicado = output<number>();

  private readonly tela = viewChild.required<ElementRef<HTMLCanvasElement>>('tela');
  private grafico: Chart | null = null;
  /** Muda quando o tema claro/escuro troca, para redesenhar com as cores novas. */
  private readonly versaoTema = signal(0);
  protected readonly descricoes = computed(() => this.series().map((s) => descreverSerie(s.nome, this.rotulos(), s.dados, this.formato())));

  constructor() {
    effect(() => {
      const configuracao = this.configuracao();
      // `untracked`: criar/atualizar o gráfico não deve religar o efeito
      untracked(() => this.desenhar(configuracao));
    });
    const observador = new MutationObserver(() => this.versaoTema.update((v) => v + 1));
    observador.observe(document.documentElement, { attributes: true, attributeFilter: ['data-tema'] });
    inject(DestroyRef).onDestroy(() => { observador.disconnect(); this.grafico?.destroy(); });
  }

  private desenhar(configuracao: ChartConfiguration): void {
    if (this.grafico) {
      this.grafico.data = configuracao.data;
      this.grafico.options = configuracao.options ?? {};
      this.grafico.update();
      return;
    }
    const contexto = this.tela().nativeElement.getContext('2d');
    if (contexto) this.grafico = new Chart(contexto, { ...configuracao, plugins: [cursorVertical] });
  }

  /** Tamanho inicial da fonte, de 11 a 24 px, conforme a largura do contêiner. */
  private tamanhoFonte(): number {
    const largura = this.tela().nativeElement.parentElement?.clientWidth ?? 600;
    return Math.round(Math.min(24, Math.max(11, largura / 60)));
  }

  /** Degradê vertical da cor da série até transparente (preenchimento sob a linha). */
  private degrade(grafico: Chart, cor: string, opacidade: number): CanvasGradient | string {
    const area = grafico.chartArea;
    if (!area) return cor + '33';
    const g = grafico.ctx.createLinearGradient(0, area.top, 0, area.bottom);
    g.addColorStop(0, cor + Math.round(opacidade * 255).toString(16).padStart(2, '0'));
    g.addColorStop(1, cor + '00');
    return g;
  }

  private configuracao(): ChartConfiguration {
    this.versaoTema();
    const tema = coresDoTema();
    const tipo = this.tipo();
    const formato = this.formato();
    const series = this.series();
    const reduzir = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    // Com pilhas nomeadas, o eixo empilha por pilha (cada pilha é uma coluna)
    const empilhar = this.empilhado() || series.some((s) => s.pilha);
    const cor = (s: SerieGrafico, i: number) => s.cor ?? CORES_GRAFICO[i % CORES_GRAFICO.length];
    const datasets = tipo === 'doughnut'
      ? [{ label: series[0]?.nome ?? '', data: series[0]?.dados ?? [], backgroundColor: this.rotulos().map((_, i) => CORES_GRAFICO[i % CORES_GRAFICO.length]), borderWidth: 2 }]
      : series.map((s, i) => ({
          type: (s.linha ? 'line' : tipo) as 'bar' | 'line', label: s.nome, data: s.dados, borderColor: cor(s, i), borderJoinStyle: 'round' as const, borderCapStyle: 'round' as const, tension: 0,
          backgroundColor: tipo === 'line' || s.linha ? (c: { chart: Chart }) => this.degrade(c.chart, cor(s, i), s.area ? 0.4 : 0.22) : cor(s, i), fill: s.area ?? (tipo === 'line' && series.length === 1),
          borderDash: s.tracejada ? [6, 4] : [],
          borderWidth: tipo === 'line' || s.linha ? 2 : 0, pointRadius: s.semPontos ? 0 : tipo === 'line' || s.linha ? 2.5 : 0, borderRadius: tipo === 'bar' && !s.linha ? 4 : 0,
          pointBackgroundColor: cor(s, i), pointHoverRadius: 5, pointHoverBorderWidth: 2, pointHoverBorderColor: tema.fundo, pointHoverBackgroundColor: cor(s, i),
          maxBarThickness: 36, ...(s.pilha ? { stack: s.pilha } : {}),
        }));
    return {
      type: tipo as 'bar',
      data: { labels: this.rotulos(), datasets: datasets as never },
      options: {
        responsive: true, maintainAspectRatio: false, animation: reduzir ? false : { duration: 300, easing: 'easeOutQuart' },
        indexAxis: this.horizontal() ? 'y' : 'x',
        interaction: { mode: tipo === 'line' ? 'index' : 'nearest', intersect: false, axis: this.horizontal() ? 'y' : 'x' },
        color: tema.apagado,
        onClick: (_e, elementos) => { if (elementos.length) this.itemClicado.emit(elementos[0].index); },
        onHover: (evento, elementos) => { const c = evento.native?.target as HTMLElement | undefined; if (c && this.clicavel()) c.style.cursor = elementos.length ? 'pointer' : 'default'; },
        plugins: {
          legend: { display: !this.semLegenda() && (series.length > 1 || tipo === 'doughnut'), position: tipo === 'doughnut' ? 'right' : 'bottom', labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, color: tema.apagado } },
          tooltip: {
            backgroundColor: tema.fundo, titleColor: tema.texto, bodyColor: tema.texto, borderColor: tema.linha, borderWidth: 1, padding: 12, cornerRadius: 12,
            boxPadding: 4, usePointStyle: true, caretSize: 0, titleFont: { weight: 'bold' },
            callbacks: { label: (c) => `${c.dataset.label ?? c.label}: ${formatarValor(Number(valorDoPonto(c.parsed, this.horizontal())), formato)}` },
          },
        },
        // Eixo das categorias (rótulos) e eixo dos valores; na barra horizontal eles trocam de lado
        scales: tipo === 'doughnut' ? {} : this.horizontal()
          ? {
              x: { type: 'linear', stacked: empilhar, beginAtZero: true, grid: { color: tema.linha }, border: { display: true, color: tema.linha }, ticks: { precision: 0, color: tema.apagado, callback: (v) => abreviar(Number(v)) } },
              y: { type: 'category', stacked: empilhar, grid: { display: false }, border: { display: true, color: tema.linha }, ticks: { color: tema.apagado } },
            }
          : {
              x: { type: 'category', stacked: empilhar, grid: { display: false }, border: { display: true, color: tema.linha }, ticks: { color: tema.apagado } },
              y: { type: 'linear', stacked: empilhar, beginAtZero: true, grid: { color: tema.linha }, border: { display: true, color: tema.linha }, ticks: { precision: 0, color: tema.apagado, callback: (v) => abreviar(Number(v)) } },
            },
        // Fonte proporcional à largura do gráfico (legível também numa TV)
        font: { size: this.tamanhoFonte() },
        onResize: (grafico, tamanho) => { grafico.options.font = { size: Math.round(Math.min(24, Math.max(11, tamanho.width / 60))) }; },
      },
    };
  }
}
