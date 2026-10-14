// Criado por José Eduardo Santana Martins
// Este arquivo serve para a visão Gantt das tarefas: barras no tempo (início → prazo), progresso, dependências, marcos e a linha de hoje.

import { afterNextRender, Component, computed, effect, ElementRef, inject, Injector, input, signal, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AvataresComponent } from './avatares.component';
import { Marco, ROTULOS_STATUS, StatusTarefa, TarefaResumo } from './tarefas.models';

type Zoom = 'dia' | 'semana' | 'mes';
type Agrupar = 'situacao' | 'responsavel' | 'marco' | 'nenhum';

const PX_POR_DIA: Record<Zoom, number> = { dia: 34, semana: 14, mes: 4 };
/** Limites do zoom contínuo (px por dia) e passo de cada clique em + ou −. */
const PX_MIN = 1.5;
const PX_MAX = 80;
const PASSO_ZOOM = 1.25;
const ALTURA_LINHA = 38;
const ALTURA_GRUPO = 30;
const DIA_MS = 86_400_000;
const CABECALHO = 52;
const ORDEM_STATUS: StatusTarefa[] = ['em_validacao', 'em_andamento', 'a_fazer', 'concluida'];

interface LinhaGantt {
  tipo: 'grupo' | 'tarefa';
  chave: string;
  y: number;
  rotulo: string;
  total?: number;
  tarefa?: TarefaResumo;
  x?: number;
  largura?: number;
  progresso?: number;
  xPrazo?: number | null;
}

/** Início do dia (local) de uma data ISO. */
const dia = (iso: string | Date): number => { const d = new Date(iso); return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(); };

/**
 * Gantt do escopo atual (equipe, minhas ou pessoa). A barra vai do início (quando foi iniciada, ou a criação) até o prazo (ou a conclusão); o
 * preenchimento é o progresso do checklist (100% se concluída); atrasadas ficam em vermelho. Setas ligam a tarefa que bloqueia à bloqueada; os
 * marcos aparecem como losangos; a linha vermelha é hoje. O que está na tela respeita os filtros do espaço. Cada barra é um link para a tarefa.
 */
@Component({
  selector: 'app-gantt-tarefas',
  imports: [RouterLink, AvataresComponent],
  template: `
    <div class="barra-gantt">
      <div class="chips-linha" role="group" aria-label="Escala do tempo">
        @for (z of zooms; track z.valor) {
          <button type="button" [class.ativo]="zoom() === z.valor" [attr.aria-pressed]="zoom() === z.valor" (click)="trocarZoom(z.valor)">{{ z.rotulo }}</button>
        }
      </div>
      <div class="zoom-gantt" role="group" aria-label="Zoom do Gantt">
        <button type="button" class="acao-secundaria acao-pequena" aria-label="Afastar (zoom out)" title="Afastar (Ctrl + rolagem para baixo)" [disabled]="px() <= pxMin" (click)="ampliar(1 / passo)">−</button>
        <output aria-live="polite">{{ porcento() }}%</output>
        <button type="button" class="acao-secundaria acao-pequena" aria-label="Aproximar (zoom in)" title="Aproximar (Ctrl + rolagem para cima)" [disabled]="px() >= pxMax" (click)="ampliar(passo)">+</button>
      </div>
      <label class="rotulo-agrupar">Agrupar por
        <select [value]="agrupar()" (change)="agrupar.set($any($event.target).value)" aria-label="Agrupar o Gantt por">
          <option value="situacao">Situação</option><option value="responsavel">Responsável</option><option value="marco">Marco</option><option value="nenhum">Sem grupos</option>
        </select>
      </label>
      <button type="button" class="acao-secundaria acao-pequena" (click)="irParaHoje()">Ir para hoje</button>
      <span class="legenda-gantt" aria-hidden="true">
        <i data-status="a_fazer"></i> A fazer <i data-status="em_andamento"></i> Em andamento <i data-status="em_validacao"></i> Em validação <i data-status="concluida"></i> Concluída <i class="atrasada"></i> Atrasada
      </span>
    </div>

    @if (!tarefas().length) {
      <p class="estado-vazio">Nenhuma tarefa para mostrar no Gantt.</p>
    } @else {
      <div class="gantt" #rolagem role="region" aria-label="Gantt das tarefas" tabindex="0" (wheel)="aoRolar($event)">
        <div class="gantt-conteudo" [style.width]="'calc(var(--rot) + ' + largura() + 'px)'">
          <!-- Cabeçalho: meses e marcas de tempo (fica no topo ao rolar) -->
          <div class="gantt-cabecalho">
            <div class="gantt-rotulo gantt-canto">Tarefa</div>
            <div class="gantt-escala" [style.width.px]="largura()">
              @for (m of meses(); track m.x) { <span class="mes" [style.left.px]="m.x" [style.width.px]="m.largura">{{ m.rotulo }}</span> }
              @for (t of marcas(); track t.x) { <span class="marca" [style.left.px]="t.x">{{ t.rotulo }}</span> }
            </div>
          </div>
          <!-- Marcos -->
          @if (marcosVisiveis().length) {
            <div class="gantt-linha gantt-marcos">
              <div class="gantt-rotulo"><strong>Marcos</strong></div>
              <div class="gantt-trilho" [style.width.px]="largura()" [style.background-size.px]="semanaPx()" [style.background-position-x.px]="deslocamentoSemana()">
                @for (m of marcosVisiveis(); track m.id) {
                  <span class="marco" [style.left.px]="m.x" [attr.data-situacao]="m.situacao" [title]="m.nome + ' — ' + m.data + ' (' + m.situacao.replace('_', ' ') + ')'"><i aria-hidden="true"></i><b>{{ m.nome }}</b></span>
                }
              </div>
            </div>
          }
          @for (l of linhas(); track l.chave) {
            @if (l.tipo === 'grupo') {
              <div class="gantt-linha gantt-grupo">
                <button type="button" class="gantt-rotulo" [attr.aria-expanded]="!fechados().has(l.chave)" (click)="alternarGrupo(l.chave)">
                  <span class="seta" [class.aberta]="!fechados().has(l.chave)" aria-hidden="true">▸</span> {{ l.rotulo }} <small>{{ l.total }}</small></button>
                <div class="gantt-trilho" [style.width.px]="largura()"></div>
              </div>
            } @else if (l.tarefa; as t) {
              <div class="gantt-linha">
                <div class="gantt-rotulo">
                  <a [routerLink]="['/tarefas', t.numero]" [title]="t.titulo + ' (Ctrl+clique abre em outra aba)'"><b>#{{ t.numero }}</b> {{ t.titulo }}</a>
                  <app-avatares [pessoas]="t.responsaveis" tamanho="pequeno" />
                </div>
                <div class="gantt-trilho" [style.width.px]="largura()" [style.background-size.px]="semanaPx()" [style.background-position-x.px]="deslocamentoSemana()">
                  <a class="barra" [routerLink]="['/tarefas', t.numero]" [attr.data-status]="t.status" [class.atrasada]="t.atrasada" [style.left.px]="l.x" [style.width.px]="l.largura"
                     [attr.aria-label]="'Tarefa ' + t.numero + ': ' + t.titulo + ', ' + rotulosStatus[t.status] + ', prazo ' + dataCurta(t.prazo)" [title]="dica(t)">
                    <span class="preenchimento" [style.width.%]="(l.progresso ?? 0) * 100"></span>
                    @if ((l.largura ?? 0) > 110) { <span class="nome-na-barra">{{ t.titulo }}</span> }
                  </a>
                  @if (l.xPrazo !== null && l.xPrazo !== undefined) { <span class="marca-prazo" [style.left.px]="l.xPrazo" title="Prazo"></span> }
                  @if ((l.largura ?? 0) <= 110) { <span class="nome-fora" [style.left.px]="(l.x ?? 0) + (l.largura ?? 0) + 6">{{ t.titulo }}</span> }
                </div>
              </div>
            }
          }
          <!-- Hoje, marcos e dependências por cima das linhas -->
          <div class="gantt-sobreposicao" style="left: var(--rot)" [style.width.px]="largura()">
            @if (hojeX() !== null) { <span class="linha-hoje" [style.left.px]="hojeX()"><small>Hoje</small></span> }
            @for (m of marcosVisiveis(); track m.id) { <span class="linha-marco" [style.left.px]="m.x"></span> }
            <svg [attr.width]="largura()" [attr.height]="alturaTotal()" aria-hidden="true">
              <defs><marker id="seta-gantt" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 8 4 0 8Z" fill="#7b8794" /></marker></defs>
              @for (s of setas(); track s.chave) { <path [attr.d]="s.d" fill="none" stroke="#7b8794" stroke-width="1.5" stroke-linecap="round" stroke-opacity="0.8" marker-end="url(#seta-gantt)" /> }
            </svg>
          </div>
        </div>
      </div>
    }
  `,
  styleUrl: './gantt-tarefas.component.scss',
})
export class GanttTarefasComponent {
  /** Tarefas já filtradas pelo espaço (busca, pessoas, marcador...). */
  readonly tarefas = input<TarefaResumo[]>([]);
  readonly marcos = input<Marco[]>([]);

  protected readonly rolagem = viewChild<ElementRef<HTMLElement>>('rolagem');
  protected readonly rotulosStatus = ROTULOS_STATUS;
  protected readonly zooms: { valor: Zoom; rotulo: string }[] = [{ valor: 'dia', rotulo: 'Dia' }, { valor: 'semana', rotulo: 'Semana' }, { valor: 'mes', rotulo: 'Mês' }];
  /** Escala atual em px por dia (contínua); os botões Dia, Semana e Mês só escolhem valores prontos. */
  protected readonly px = signal(PX_POR_DIA.semana);
  protected readonly zoom = computed<Zoom | null>(() => (Object.keys(PX_POR_DIA) as Zoom[]).find((z) => Math.abs(PX_POR_DIA[z] - this.px()) < 0.01) ?? null);
  protected readonly porcento = computed(() => Math.round((this.px() / PX_POR_DIA.semana) * 100));
  protected readonly pxMin = PX_MIN;
  protected readonly pxMax = PX_MAX;
  protected readonly passo = PASSO_ZOOM;
  private readonly injetor = inject(Injector);
  protected readonly agrupar = signal<Agrupar>('situacao');
  protected readonly fechados = signal<ReadonlySet<string>>(new Set(['situacao:concluida']));
  private jaRolou = false;


  /**
   * Início de cada tarefa na barra. Quem já começou usa a data real; quem ainda não começou e é bloqueada por outras tarefas da tela
   * começa onde a última bloqueadora termina (conclusão ou prazo); as demais, na criação.
   */
  private readonly inicios = computed(() => {
    const porNumero = new Map(this.tarefas().map((t) => [t.numero, t]));
    const memo = new Map<number, number>();
    const emCalculo = new Set<number>();
    const fimDe = (t: TarefaResumo) => dia(t.concluida_em ?? t.prazo);
    const inicioDe = (t: TarefaResumo): number => {
      const pronto = memo.get(t.numero);
      if (pronto !== undefined) return pronto;
      const real = dia(t.iniciada_em ?? t.criado_em);
      let inicio = real;
      if (!t.iniciada_em && !emCalculo.has(t.numero)) {
        emCalculo.add(t.numero);
        for (const n of t.bloqueada_por_numeros ?? []) {
          const b = porNumero.get(n);
          if (b) inicio = Math.max(inicio, fimDe(b));
        }
        emCalculo.delete(t.numero);
        // Nunca depois do prazo da própria tarefa
        if (inicio > dia(t.prazo)) inicio = Math.max(real, dia(t.prazo) - DIA_MS);
      }
      memo.set(t.numero, inicio);
      return inicio;
    };
    for (const t of this.tarefas()) inicioDe(t);
    return memo;
  });

  private inicioDaBarra(t: TarefaResumo): number {
    return this.inicios().get(t.numero) ?? dia(t.iniciada_em ?? t.criado_em);
  }

  /** Intervalo do gráfico: do primeiro início/marco até o último prazo/hoje, com folga. */
  private readonly intervalo = computed(() => {
    const datas: number[] = [dia(new Date())];
    for (const t of this.tarefas()) {
      datas.push(this.inicioDaBarra(t), dia(t.prazo));
      if (t.concluida_em) datas.push(dia(t.concluida_em));
    }
    for (const m of this.marcos()) datas.push(dia(m.data_alvo + 'T12:00:00'));
    return { ini: Math.min(...datas) - 3 * DIA_MS, fim: Math.max(...datas) + 10 * DIA_MS };
  });

  protected readonly largura = computed(() => Math.max(600, Math.round(((this.intervalo().fim - this.intervalo().ini) / DIA_MS) * this.px())));
  protected readonly semanaPx = computed(() => this.px() * 7);
  /** Deslocamento para as linhas de semana caírem nas segundas-feiras. */
  protected readonly deslocamentoSemana = computed(() => {
    const ini = new Date(this.intervalo().ini);
    const ate = (8 - ini.getDay()) % 7; // dias até a próxima segunda
    return ate * this.px();
  });

  private x(ms: number): number {
    return Math.round(((ms - this.intervalo().ini) / DIA_MS) * this.px());
  }

  protected readonly hojeX = computed<number | null>(() => this.x(dia(new Date())) + Math.round(this.px() / 2));

  protected readonly meses = computed(() => {
    const { ini, fim } = this.intervalo();
    const saida: { x: number; largura: number; rotulo: string }[] = [];
    let cursor = new Date(ini);
    cursor = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    while (cursor.getTime() < fim) {
      const proximo = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
      const x = Math.max(0, this.x(cursor.getTime()));
      const xFim = Math.min(this.largura(), this.x(proximo.getTime()));
      saida.push({ x, largura: Math.max(0, xFim - x), rotulo: cursor.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }) });
      cursor = proximo;
    }
    return saida;
  });

  /** Marcas de tempo: cada dia (zoom dia), cada segunda-feira (semana) ou nada (mês, só os meses). */
  protected readonly marcas = computed(() => {
    // Densidade conforme a escala: todos os dias, só as segundas-feiras ou nenhuma marca (só os meses)
    const px = this.px();
    const zoom: Zoom = px >= 24 ? 'dia' : px >= 9 ? 'semana' : 'mes';
    if (zoom === 'mes') return [];
    const { ini, fim } = this.intervalo();
    const saida: { x: number; rotulo: string }[] = [];
    for (let t = ini; t < fim; t += DIA_MS) {
      const d = new Date(t);
      if (zoom === 'semana' && d.getDay() !== 1) continue;
      saida.push({ x: this.x(t), rotulo: zoom === 'dia' ? String(d.getDate()) : `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}` });
    }
    return saida;
  });

  protected readonly marcosVisiveis = computed(() => this.marcos().map((m) => ({ ...m, x: this.x(dia(m.data_alvo + 'T12:00:00')) + Math.round(this.px() / 2), data: new Date(m.data_alvo + 'T12:00:00').toLocaleDateString('pt-BR') })));

  /** Linhas do gráfico, já com a posição de cada barra. */
  protected readonly linhas = computed<LinhaGantt[]>(() => {
    const grupos = new Map<string, { rotulo: string; ordem: number; itens: TarefaResumo[] }>();
    const modo = this.agrupar();
    const marcosPorId = new Map(this.marcos().map((m) => [m.id, m.nome]));
    for (const t of this.tarefas()) {
      let chave = 'todas', rotulo = 'Todas as tarefas', ordem = 0;
      if (modo === 'situacao') { chave = `situacao:${t.status}`; rotulo = ROTULOS_STATUS[t.status]; ordem = ORDEM_STATUS.indexOf(t.status); }
      else if (modo === 'responsavel') { const r = t.responsaveis[0]; chave = `resp:${r?.id ?? 0}`; rotulo = r?.nome ?? 'Sem responsável'; ordem = r ? 1 : 2; }
      else if (modo === 'marco') { chave = `marco:${t.marco_id ?? ''}`; rotulo = t.marco_id ? marcosPorId.get(t.marco_id) ?? 'Marco' : 'Sem marco'; ordem = t.marco_id ? 1 : 2; }
      const g = grupos.get(chave) ?? { rotulo, ordem, itens: [] };
      g.itens.push(t);
      grupos.set(chave, g);
    }
    const ordenados = [...grupos.entries()].sort((a, b) => a[1].ordem - b[1].ordem || a[1].rotulo.localeCompare(b[1].rotulo));
    const saida: LinhaGantt[] = [];
    let y = 0;
    for (const [chave, g] of ordenados) {
      g.itens.sort((a, b) => this.inicioDaBarra(a) - this.inicioDaBarra(b) || a.numero - b.numero);
      if (modo !== 'nenhum') { saida.push({ tipo: 'grupo', chave, y, rotulo: g.rotulo, total: g.itens.length }); y += ALTURA_GRUPO; }
      if (this.fechados().has(chave)) continue;
      for (const t of g.itens) {
        const inicio = this.inicioDaBarra(t);
        let fim = dia(t.concluida_em ?? t.prazo);
        if (fim <= inicio) fim = inicio + DIA_MS;
        const x = this.x(inicio);
        const progresso = t.status === 'concluida' ? 1 : t.checklist_total ? t.checklist_feitos / t.checklist_total : 0;
        const prazoX = t.concluida_em && dia(t.prazo) !== dia(t.concluida_em) ? this.x(dia(t.prazo)) + Math.round(this.px() / 2) : null;
        saida.push({ tipo: 'tarefa', chave: `t${t.numero}`, y, rotulo: t.titulo, tarefa: t, x, largura: Math.max(8, this.x(fim) - x + (fim === inicio + DIA_MS ? 0 : Math.round(this.px() / 2))), progresso, xPrazo: prazoX });
        y += ALTURA_LINHA;
      }
    }
    return saida;
  });

  private readonly alturaMarcos = computed(() => (this.marcosVisiveis().length ? ALTURA_LINHA : 0));
  protected readonly alturaTotal = computed(() => this.linhas().reduce((total, l) => total + (l.tipo === 'grupo' ? ALTURA_GRUPO : ALTURA_LINHA), 0) + this.alturaMarcos() + CABECALHO);

  /** Setas da tarefa que bloqueia para a bloqueada (só entre as que estão na tela). */
  protected readonly setas = computed(() => {
    const porNumero = new Map(this.linhas().filter((l) => l.tarefa).map((l) => [l.tarefa!.numero, l]));
    const topo = CABECALHO + this.alturaMarcos();
    const saida: { chave: string; d: string }[] = [];
    for (const destino of porNumero.values()) {
      for (const n of destino.tarefa!.bloqueada_por_numeros ?? []) {
        const origem = porNumero.get(n);
        if (!origem) continue;
        const x1 = (origem.x ?? 0) + (origem.largura ?? 0);
        const y1 = topo + origem.y + ALTURA_LINHA / 2;
        const x2 = destino.x ?? 0;
        const y2 = topo + destino.y + ALTURA_LINHA / 2;
        // Curva suave (Bézier): sai na horizontal da bloqueadora e entra na horizontal na bloqueada
        const k = Math.max(20, Math.min(90, Math.abs(x2 - x1) / 2));
        const d = `M${x1},${y1} C${x1 + k},${y1} ${x2 - k - 2},${y2} ${x2 - 2},${y2}`;
        saida.push({ chave: `${n}-${destino.tarefa!.numero}`, d });
      }
    }
    return saida;
  });

  constructor() {
    // Ao aparecer pela primeira vez, rola até hoje (um pouco antes, para ver o que vem logo antes)
    effect(() => {
      const el = this.rolagem()?.nativeElement;
      if (el && this.tarefas().length && !this.jaRolou) { this.jaRolou = true; queueMicrotask(() => this.irParaHoje()); }
    });
  }

  /** Troca a escala e mantém a linha de hoje à vista (a largura muda, então a rolagem anterior perde o sentido). */
  protected trocarZoom(valor: Zoom): void {
    this.px.set(PX_POR_DIA[valor]);
    setTimeout(() => this.irParaHoje());
  }

  /** Multiplica a escala (zoom in/out) mantendo parado o dia sob `ancoraX` (px da janela) ou, sem ele, o do centro da tela. */
  protected ampliar(fator: number, ancoraX?: number): void {
    const el = this.rolagem()?.nativeElement;
    const antes = this.px();
    const depois = Math.min(PX_MAX, Math.max(PX_MIN, antes * fator));
    if (depois === antes) return;
    if (!el) { this.px.set(depois); return; }
    const rotulo = el.querySelector<HTMLElement>('.gantt-canto')?.offsetWidth ?? 0;
    const ancora = ancoraX !== undefined ? ancoraX - el.getBoundingClientRect().left : (el.clientWidth + rotulo) / 2;
    const dias = (el.scrollLeft + ancora - rotulo) / antes;
    this.px.set(depois);
    afterNextRender(() => { el.scrollLeft = Math.max(0, dias * depois + rotulo - ancora); }, { injector: this.injetor });
  }

  /** Ctrl (ou Cmd) + roda do mouse aproxima e afasta; a rolagem normal segue como está. */
  protected aoRolar(evento: WheelEvent): void {
    if (!evento.ctrlKey && !evento.metaKey) return;
    evento.preventDefault();
    this.ampliar(evento.deltaY < 0 ? 1.15 : 1 / 1.15, evento.clientX);
  }

  protected irParaHoje(): void {
    const el = this.rolagem()?.nativeElement;
    const x = this.hojeX();
    if (el && x !== null) el.scrollTo?.({ left: Math.max(0, x - 160), behavior: 'auto' });
  }

  protected alternarGrupo(chave: string): void {
    this.fechados.update((s) => { const n = new Set(s); n.has(chave) ? n.delete(chave) : n.add(chave); return n; });
  }

  protected dataCurta(iso: string): string {
    return new Date(iso).toLocaleDateString('pt-BR');
  }

  protected dica(t: TarefaResumo): string {
    const quem = t.responsaveis.map((p) => p.nome).join(', ') || 'sem responsável';
    const checklist = t.checklist_total ? ` · checklist ${t.checklist_feitos}/${t.checklist_total}` : '';
    return `#${t.numero} ${t.titulo}\n${ROTULOS_STATUS[t.status]}${t.atrasada ? ' (atrasada)' : ''} · ${quem}\nInício ${t.iniciada_em ? this.dataCurta(t.iniciada_em) : t.bloqueada_por_numeros?.length ? 'previsto ' + this.dataCurta(new Date(this.inicioDaBarra(t)).toISOString()) : this.dataCurta(t.criado_em)} · prazo ${this.dataCurta(t.prazo)}${t.concluida_em ? ' · concluída ' + this.dataCurta(t.concluida_em) : ''}${checklist}${t.bloqueada ? '\nBloqueada por outra tarefa' : ''}`;
  }
}

