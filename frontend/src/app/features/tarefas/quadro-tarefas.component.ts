// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o quadro de tarefas (estilo Trello): colunas do pipeline, raias por pessoa, arraste e criação rápida.

import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, DestroyRef, effect, ElementRef, inject, input, output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AvataresComponent } from './avatares.component';
import { CartaoTarefaComponent } from './cartao-tarefa.component';
import { escolherNivel, NivelDensidade } from './densidade-quadro';
import { PALETA_MARCADORES } from './marcadores.paleta';
import { agruparRaias, Estagio, Pessoa, PessoaCarga, ROTULOS_PRIORIDADE, STATUS, StatusTarefa, TarefaResumo } from './tarefas.models';

/** Quantas concluídas a coluna mostra antes do "ver todas". */
const LIMITE_CONCLUIDAS = 10;
/** Chave (localStorage) da coluna Concluída recolhida. */
const CHAVE_RECOLHIDA = 'tarefas.quadro.concluida-recolhida';

/** Movimento pedido pelo quadro (arraste ou menu do cartão); o espaço decide a ação do pipeline. */
export interface MovimentoQuadro { tarefa: TarefaResumo; para: StatusTarefa; /** Coluna (estágio) de destino quando a equipe tem estágios. */ estagioId?: string }

/** Opção do menu "⋯" do cartão. */
interface OpcaoMenu { rotulo: string; para: StatusTarefa }

@Component({
  selector: 'app-quadro-tarefas',
  imports: [FormsModule, DecimalPipe, DatePipe, CartaoTarefaComponent, AvataresComponent],
  // Clique fora do menu "⋯" o fecha (o botão do menu interrompe a propagação do próprio clique)
  host: { '(document:click)': 'menuAberto.set(null)', '(window:resize)': 'agendarDensidade()', '(window:scroll)': 'dica.set(null)' },
  template: `
    @for (raia of raias(); track raia.chave) {
      @if (comRaias()) {
        <!-- Cabeçalho da raia: a pessoa, a carga e quantas tarefas tem no quadro -->
        <div class="cabecalho-raia">
          @if (raia.pessoa; as p) { <app-avatares [pessoas]="[p]" /> <strong>{{ p.nome }}</strong> } @else { <strong>Sem responsável</strong> }
          <small>{{ raia.total }} tarefa{{ raia.total === 1 ? '' : 's' }}</small>
          @if (raia.carga; as c) {
            <span class="faixa-carga" [attr.data-faixa]="c.faixa" title="Carga de todas as tarefas da pessoa">{{ c.faixa }} · {{ c.carga | number: '1.0-1' }} pts</span>
          }
        </div>
      }
      <div class="quadro" [class.com-raias]="comRaias()">
        @for (c of raia.colunas; track c.chave) {
          <section class="lista-quadro" [attr.data-status]="c.categoria" [style.--cor-estagio]="c.cor" [class.alvo]="alvo() === raia.chave + c.chave"
                   [class.recolhida]="c.categoria === 'concluida' && recolhida()" [attr.aria-label]="c.rotulo"
                   (dragover)="$event.preventDefault(); alvo.set(raia.chave + c.chave)" (dragleave)="alvo.set(null)" (drop)="soltar($event, c)">
            <header>
              <h3>{{ c.rotulo }}</h3><span class="contagem">{{ c.total }}</span>
              @if (c.categoria === 'concluida') {
                <button type="button" class="botao-icone" [attr.aria-label]="recolhida() ? 'Expandir Concluída' : 'Recolher Concluída'"
                        [title]="recolhida() ? 'Expandir' : 'Recolher'" (click)="alternarRecolhida()">{{ recolhida() ? '⟩' : '⟨' }}</button>
              }
            </header>
            @if (!(c.categoria === 'concluida' && recolhida())) {
              <!-- data-nivel: densidade escolhida pelo quadro para esta coluna (1 normal, 2 duas subcolunas, 3 compacto, 4 reduzido) -->
              <div class="cartoes" [attr.data-col]="raia.chave + c.chave" [attr.data-nivel]="nivelDe(raia.chave + c.chave)">
                @for (t of c.itens; track t.numero) {
                  <div class="envoltorio-cartao" draggable="true" [class.arrastando]="arrastando()?.numero === t.numero"
                       (dragstart)="iniciarArraste($event, t); dica.set(null)" (dragend)="terminarArraste()"
                       (mouseenter)="mostrarDica($event, t, raia.chave + c.chave)" (mouseleave)="dica.set(null)"
                       (focusin)="mostrarDica($event, t, raia.chave + c.chave)" (focusout)="dica.set(null)">
                    <app-cartao-tarefa [tarefa]="t" [destacado]="destacado() === t.numero" (abrir)="abrir.emit($event)" />
                    @if (opcoes(t).length) {
                      <button type="button" class="menu-cartao" [attr.aria-label]="'Ações da tarefa ' + t.numero" [attr.aria-expanded]="menuAberto() === t.numero"
                              (click)="$event.stopPropagation(); menuAberto.set(menuAberto() === t.numero ? null : t.numero)">⋯</button>
                      @if (menuAberto() === t.numero) {
                        <div class="menu-suspenso" role="menu">
                          @for (o of opcoes(t); track o.rotulo) {
                            <button type="button" role="menuitem" (click)="menuAberto.set(null); mover.emit({ tarefa: t, para: o.para })">{{ o.rotulo }}</button>
                          }
                        </div>
                      }
                    }
                  </div>
                } @empty { <p class="lista-vazia">{{ c.categoria === 'a_fazer' && c.primeira && podeCriar() ? 'Nada a fazer por aqui.' : 'Nenhuma tarefa' }}</p> }
                @if (c.categoria === 'concluida' && c.total > c.itens.length) {
                  <button type="button" class="link-simples ver-todas-concluidas" (click)="todasConcluidas.set(true)">Ver todas as {{ c.total }}</button>
                }
              </div>
              <!-- Criação rápida: só o título; o restante segue os padrões e pode ser ajustado na tarefa -->
              @if (c.categoria === 'a_fazer' && c.primeira && podeCriar() && !comRaias()) {
                @if (criando()) {
                  <form class="criacao-rapida" (submit)="$event.preventDefault(); confirmarCriacao()">
                    <textarea #campoCriacao name="titulo" rows="2" maxlength="200" placeholder="Título da tarefa" aria-label="Título da nova tarefa"
                              [(ngModel)]="novoTitulo" (keydown.enter)="$event.preventDefault(); confirmarCriacao()" (keydown.escape)="cancelarCriacao()"></textarea>
                    <small>Enter cria · responsável: você · prazo em 7 dias, 18:00 · Esc cancela</small>
                    <div class="acoes-criacao">
                      <button type="submit" class="acao-primaria" [disabled]="!novoTitulo.trim()">Adicionar</button>
                      <button type="button" class="botao-icone" aria-label="Cancelar" (click)="cancelarCriacao()">×</button>
                    </div>
                  </form>
                } @else {
                  <button type="button" class="adicionar-cartao" (click)="abrirCriacao()">+ Adicionar tarefa</button>
                }
              }
            }
          </section>
        }
      </div>
    }

    <!-- Dica do cartão reduzido: tudo da tarefa, já que o cartão só mostra número, prazo, criticidade e marcadores -->
    @if (dica(); as d) {
      <div class="dica-tarefa" role="tooltip" [style.left.px]="d.x" [style.top.px]="d.y">
        <strong>#{{ d.tarefa.numero }} · {{ d.tarefa.titulo }}</strong>
        <span>Prazo: {{ d.tarefa.prazo | date: 'dd/MM/yyyy HH:mm' }} · Prioridade: {{ rotulosPrioridade[d.tarefa.prioridade] }}</span>
        @if (d.tarefa.responsaveis.length) { <span>Responsáveis: {{ nomes(d.tarefa) }}</span> }
        @if (d.tarefa.marcadores.length) { <span>Marcadores: {{ nomesMarcadores(d.tarefa) }}</span> }
        @if (d.tarefa.checklist_total || d.tarefa.comentarios || d.tarefa.anexos) {
          <span>@if (d.tarefa.checklist_total) { Checklist {{ d.tarefa.checklist_feitos }}/{{ d.tarefa.checklist_total }} · }Comentários {{ d.tarefa.comentarios }} · Anexos {{ d.tarefa.anexos }}</span>
        }
        @if (d.tarefa.controlada_externamente) { <span>📄 Controlada pelo módulo Contratos</span> }
      </div>
    }
  `,
})
export class QuadroTarefasComponent {
  /** Tarefas já filtradas pelo espaço. */
  readonly itens = input<TarefaResumo[]>([]);
  /** Colunas da equipe (estágios); vazio = as 4 situações padrão. */
  readonly estagios = input<Estagio[]>([]);
  /** Agrupar em raias por responsável. */
  readonly comRaias = input(false);
  /** Carga das pessoas (cabeçalho das raias), quando disponível. */
  readonly cargas = input<PessoaCarga[]>([]);
  /** O usuário lidera o contexto (vê "Validar" e "Devolver" no menu). */
  readonly lider = input(false);
  /** Mostrar a criação rápida na coluna A fazer. */
  readonly podeCriar = input(false);
  /** Tarefa em destaque (recém-criada). */
  readonly destacado = input<number | null>(null);

  readonly abrir = output<number>();
  readonly mover = output<MovimentoQuadro>();
  readonly criar = output<string>();

  // Estado do arraste, do menu e da criação rápida
  protected readonly arrastando = signal<TarefaResumo | null>(null);
  protected readonly alvo = signal<string | null>(null);
  protected readonly menuAberto = signal<number | null>(null);
  protected readonly criando = signal(false);
  protected readonly todasConcluidas = signal(false);
  protected readonly recolhida = signal(lerRecolhida());
  protected novoTitulo = '';
  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;
  /** Densidade de cada coluna (chave da raia + coluna), escolhida pelo quadro conforme o espaço e a quantidade de cartões. */
  protected readonly niveis = signal<Record<string, NivelDensidade>>({});
  /** Dica do cartão reduzido (posição na tela e tarefa). */
  protected readonly dica = signal<{ tarefa: TarefaResumo; x: number; y: number } | null>(null);
  private readonly hospedeiro = inject<ElementRef<HTMLElement>>(ElementRef);
  private quadroAgendado = 0;
  private readonly campoCriacao = viewChild<ElementRef<HTMLTextAreaElement>>('campoCriacao');

  constructor() {
    // Mudou o que está na tela (tarefas, colunas, Concluída): mede de novo. Mudou o tamanho do quadro (janela, tela cheia): idem.
    effect(() => {
      this.raias();
      this.recolhida();
      this.criando();
      this.agendarDensidade();
    });
    const observador = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => this.agendarDensidade());
    observador?.observe(this.hospedeiro.nativeElement);
    inject(DestroyRef).onDestroy(() => {
      observador?.disconnect();
      cancelAnimationFrame(this.quadroAgendado);
    });
  }

  protected nivelDe(chave: string): NivelDensidade {
    return this.niveis()[chave] ?? 1;
  }

  /** Reavalia a densidade no próximo quadro de animação (depois que o Angular atualizou a tela, antes de pintar). */
  protected agendarDensidade(): void {
    cancelAnimationFrame(this.quadroAgendado);
    this.quadroAgendado = requestAnimationFrame(() => this.ajustarDensidade());
  }

  /**
   * Para cada coluna, aplica cada nível (1, 2, 3) e fica no primeiro em que os cartões cabem sem rolagem. Tudo na mesma passagem, antes da
   * pintura: não há piscada. Se nem o nível 3 couber, a rolagem da coluna é o último recurso.
   */
  private ajustarDensidade(): void {
    const colunas = this.hospedeiro.nativeElement.querySelectorAll<HTMLElement>('.cartoes[data-col]');
    const novos: Record<string, NivelDensidade> = {};
    colunas.forEach((el) => {
      const chave = el.dataset['col'] ?? '';
      novos[chave] = escolherNivel((nivel) => {
        el.dataset['nivel'] = String(nivel);
        return el.scrollHeight <= el.clientHeight + 1;
      }, el.parentElement?.clientWidth ?? 0);
    });
    const antes = this.niveis();
    const mudou = Object.keys(novos).length !== Object.keys(antes).length || Object.entries(novos).some(([k, v]) => antes[k] !== v);
    if (mudou) this.niveis.set(novos);
  }

  // --- Dica do cartão reduzido -----------------------------------------------------------------------

  protected mostrarDica(evento: Event, t: TarefaResumo, coluna: string): void {
    if (this.nivelDe(coluna) !== 4 || this.arrastando()) {
      this.dica.set(null);
      return;
    }
    const caixa = (evento.currentTarget as HTMLElement).getBoundingClientRect();
    const largura = 320;
    // À direita do cartão; sem espaço, à esquerda; sempre dentro da janela
    const x = caixa.right + 8 + largura <= window.innerWidth ? caixa.right + 8 : Math.max(8, caixa.left - largura - 8);
    this.dica.set({ tarefa: t, x, y: Math.max(8, Math.min(caixa.top, window.innerHeight - 180)) });
  }

  protected nomes(t: TarefaResumo): string {
    return t.responsaveis.map((p) => p.nome).join(', ');
  }

  protected nomesMarcadores(t: TarefaResumo): string {
    return t.marcadores.map((m) => m.nome).join(', ');
  }

  /** Raias (uma só, sem cabeçalho, quando não agrupa), cada uma com as quatro colunas. */
  protected readonly raias = computed(() => {
    const cargas = new Map(this.cargas().map((c) => [c.id, c]));
    const grupos: { pessoa: Pessoa | null; itens: TarefaResumo[] }[] = this.comRaias() ? agruparRaias(this.itens()) : [{ pessoa: null, itens: this.itens() }];
    return grupos.map((g) => ({
      chave: g.pessoa ? `p${g.pessoa.id}-` : 'sem-',
      pessoa: g.pessoa,
      total: g.itens.length,
      carga: g.pessoa ? cargas.get(g.pessoa.id) ?? null : null,
      colunas: this.colunasDe(g.itens),
    }));
  });

  /** Colunas da raia: os estágios da equipe (cada tarefa na sua coluna) ou, sem estágios, as 4 situações. */
  private colunasDe(itens: TarefaResumo[]) {
    const estagios = this.estagios();
    const base = estagios.length
      ? estagios.map((e, i) => ({ chave: e.id, categoria: e.categoria, rotulo: e.nome, estagioId: e.id, cor: PALETA_MARCADORES[e.cor_indice]?.borda ?? '#8f8f8f',
          primeira: estagios.findIndex((x) => x.categoria === e.categoria) === i }))
      : STATUS.map((st) => ({ chave: st.valor as string, categoria: st.valor, rotulo: st.rotulo, estagioId: undefined as string | undefined, cor: 'transparent', primeira: true }));
    const primeiraDe = new Map(base.filter((c) => c.primeira).map((c) => [c.categoria, c.chave]));
    return base.map((c) => {
      // Tarefa sem estágio (ou com estágio que saiu da equipe) fica na primeira coluna da situação dela
      const todos = itens.filter((t) => (estagios.length && t.estagio_id && estagios.some((e) => e.id === t.estagio_id) ? t.estagio_id : primeiraDe.get(t.status)) === c.chave);
      // Abertas: sempre em ordem crescente de prazo (as mais urgentes no alto), desempate pelo número
      if (c.categoria !== 'concluida') return { ...c, itens: [...todos].sort((a, b) => a.prazo.localeCompare(b.prazo) || a.numero - b.numero), total: todos.length };
      // Concluídas: as mais recentes primeiro, limitadas até o "ver todas"
      const recentes = [...todos].sort((a, b) => (b.concluida_em ?? b.atualizado_em).localeCompare(a.concluida_em ?? a.atualizado_em));
      return { ...c, itens: this.todasConcluidas() ? recentes : recentes.slice(0, LIMITE_CONCLUIDAS), total: todos.length };
    });
  }

  /** Movimentos oferecidos no menu "⋯" (a API confere a permissão; em recusa, nada muda). */
  protected opcoes(t: TarefaResumo): OpcaoMenu[] {
    switch (t.status) {
      case 'a_fazer': return [{ rotulo: 'Iniciar', para: 'em_andamento' }, ...(this.lider() ? [{ rotulo: 'Concluir', para: 'concluida' as StatusTarefa }] : [])];
      case 'em_andamento': return [
        { rotulo: t.equipe ? 'Entregar para validação' : 'Concluir', para: t.equipe ? 'em_validacao' : 'concluida' },
        { rotulo: 'Voltar para A fazer', para: 'a_fazer' },
      ];
      case 'em_validacao': return this.lider() ? [{ rotulo: 'Validar', para: 'concluida' }, { rotulo: 'Devolver', para: 'em_andamento' }] : [];
      default: return this.lider() ? [{ rotulo: 'Reabrir', para: 'em_andamento' }] : [];
    }
  }

  // --- Arraste entre colunas --------------------------------------------------------------------------

  protected iniciarArraste(evento: DragEvent, t: TarefaResumo): void {
    this.arrastando.set(t);
    evento.dataTransfer?.setData('text/plain', String(t.numero));
    if (evento.dataTransfer) evento.dataTransfer.effectAllowed = 'move';
  }

  protected terminarArraste(): void {
    this.arrastando.set(null);
    this.alvo.set(null);
  }

  protected soltar(evento: DragEvent, coluna: { categoria: StatusTarefa; estagioId?: string }): void {
    evento.preventDefault();
    const t = this.arrastando();
    this.terminarArraste();
    // Muda de situação ou, na mesma situação, de coluna (estágio)
    if (t && (t.status !== coluna.categoria || (coluna.estagioId && coluna.estagioId !== t.estagio_id))) this.mover.emit({ tarefa: t, para: coluna.categoria, estagioId: coluna.estagioId });
  }

  // --- Coluna Concluída recolhível (preferência guardada no navegador) --------------------------------

  protected alternarRecolhida(): void {
    this.recolhida.update((v) => !v);
    try {
      localStorage.setItem(CHAVE_RECOLHIDA, this.recolhida() ? '1' : '0');
    } catch {
      // Navegador sem armazenamento (janela privada): a preferência só vale nesta visita
    }
  }

  // --- Criação rápida ---------------------------------------------------------------------------------

  protected abrirCriacao(): void {
    this.novoTitulo = '';
    this.criando.set(true);
    // Foco no campo depois que ele aparece
    setTimeout(() => this.campoCriacao()?.nativeElement.focus());
  }

  protected cancelarCriacao(): void {
    this.criando.set(false);
    this.novoTitulo = '';
  }

  protected confirmarCriacao(): void {
    const titulo = this.novoTitulo.trim();
    if (!titulo) return;
    this.criar.emit(titulo);
    // Mantém o campo aberto e vazio, para criar várias em sequência (como no Trello)
    this.novoTitulo = '';
    setTimeout(() => this.campoCriacao()?.nativeElement.focus());
  }
}

/** Lê a preferência da coluna Concluída; sem armazenamento disponível, começa expandida. */
function lerRecolhida(): boolean {
  try {
    return localStorage.getItem(CHAVE_RECOLHIDA) === '1';
  } catch {
    return false;
  }
}
